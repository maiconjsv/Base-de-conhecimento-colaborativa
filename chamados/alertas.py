"""Regras dos alertas do Acompanhamento de Chamados (funcoes puras).

Um chamado ativo (status fora de `status_pausados`) gera alerta quando:
- CADENCIA: passou `cadencia` minutos desde o ultimo acompanhamento
  ("sem acompanhamento ha 1 h 10 min"). A cadencia e a do chamado ou, se nao
  tiver, a padrao da prioridade.
- PRAZO: faltam N minutos para o prazo, para cada N em `prazo_avisos`
  (cada aviso uma vez so por prazo).
- ATRASO: o prazo passou; repete a cada `atraso_repetir_min`.

Nada dispara enquanto o chamado estiver adiado (`adiado_ate`) nem fora do
horario de trabalho (exceto P1, se `p1_fora_do_horario`). Os alertas de um
mesmo chamado saem juntos, num item so, com todos os motivos.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from .store import Ticket


@dataclass
class Alert:
    ticket: Ticket
    reasons: list[str] = field(default_factory=list)
    severity: int = 0                    # 0 = lembrete, 1 = prazo perto, 2 = atrasado
    deadline_marks: list[int] = field(default_factory=list)   # avisos de prazo a gravar
    overdue_mark: bool = False


def fmt_duration(minutes: float) -> str:
    """75 -> '1 h 15 min'; 1500 -> '1 dia 1 h'."""
    m = int(round(abs(minutes)))
    if m < 1:
        return "menos de 1 min"
    days, rest = divmod(m, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} dia{'s' if days > 1 else ''}" + (f" {hours} h" if hours else "")
    if hours:
        return f"{hours} h" + (f" {mins} min" if mins else "")
    return f"{mins} min"


def _hhmm(text: str, default: time) -> time:
    try:
        h, m = text.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return default


def in_work_hours(now: datetime, settings: dict) -> bool:
    if now.weekday() not in settings.get("dias_uteis", [0, 1, 2, 3, 4]):
        return False
    start = _hhmm(settings.get("horario_inicio", "08:00"), time(8))
    end = _hhmm(settings.get("horario_fim", "18:00"), time(18))
    return start <= now.time() < end


def is_paused(t: Ticket, settings: dict) -> bool:
    return t.status in settings.get("status_pausados", [])


def cadence_minutes(t: Ticket, settings: dict) -> int:
    """Notificar cobranca a cada X minutos. 0 = nao notificar (so avisos de prazo).

    `cadencia_min` do chamado: None = padrao da prioridade; 0 = desligado.
    """
    if t.cadencia_min is not None:
        return max(0, int(t.cadencia_min))
    return int(settings.get("cadencia", {}).get(t.prioridade, 240))


def cadence_label(t: Ticket, settings: dict) -> str:
    """Texto curto da coluna "Notificar": "a cada 1 h", "padrão (4 h)", "desligado"."""
    minutes = cadence_minutes(t, settings)
    if minutes == 0:
        return "desligado"
    if t.cadencia_min is None:
        return f"padrão ({fmt_duration(minutes)})"
    return f"a cada {fmt_duration(minutes)}"


def followup_at(t: Ticket, settings: dict) -> datetime:
    """Quando o chamado passa a cobrar acompanhamento (considerando adiamento)."""
    if cadence_minutes(t, settings) == 0:
        return datetime.max
    due = t.ultimo_toque + timedelta(minutes=cadence_minutes(t, settings))
    if t.adiado_ate and t.adiado_ate > due:
        return t.adiado_ate
    return due


def due_alerts(tickets: list[Ticket], settings: dict, now: datetime) -> list[Alert]:
    alerts = []
    working = in_work_hours(now, settings)
    pres = sorted({int(p) for p in settings.get("prazo_avisos", []) if int(p) > 0}, reverse=True)
    repeat = timedelta(minutes=int(settings.get("atraso_repetir_min", 15)))

    for t in tickets:
        if is_paused(t, settings):
            continue
        if t.adiado_ate and now < t.adiado_ate:
            continue
        if not working and not (t.prioridade == "P1" and settings.get("p1_fora_do_horario", True)):
            continue

        a = Alert(ticket=t)
        if t.prazo:
            left = (t.prazo - now).total_seconds() / 60
            if left <= 0:
                if t.ultimo_aviso_atraso is None or now - t.ultimo_aviso_atraso >= repeat:
                    a.reasons.append(f"Prazo estourado há {fmt_duration(-left)}")
                    a.severity = 2
                    a.overdue_mark = True
            else:
                pending = [p for p in pres if left <= p and p not in t.prazo_avisos_feitos]
                if pending:
                    a.reasons.append(f"Prazo vence em {fmt_duration(left)} ({t.prazo:%d/%m %H:%M})")
                    a.severity = max(a.severity, 1)
                    a.deadline_marks = pending

        since = (now - t.ultimo_toque).total_seconds() / 60
        cadence = cadence_minutes(t, settings)
        if cadence and since >= cadence:
            a.reasons.append(f"Sem acompanhamento há {fmt_duration(since)}")

        if a.reasons:
            alerts.append(a)

    alerts.sort(key=lambda x: (-x.severity, x.ticket.prioridade, x.ticket.numero))
    return alerts


def follow_label(t: Ticket, settings: dict, now: datetime) -> tuple[str, int]:
    """Texto da coluna "Próxima cobrança" e nivel (0 ok, 1 perto, 2 vencida, -1 pausado)."""
    if is_paused(t, settings):
        return "pausado", -1
    if t.adiado_ate and now < t.adiado_ate:
        return f"adiado até {t.adiado_ate:%H:%M}" if t.adiado_ate.date() == now.date() \
            else f"adiado até {t.adiado_ate:%d/%m %H:%M}", 0
    if cadence_minutes(t, settings) == 0:
        return "sem aviso periódico", 0
    left = (followup_at(t, settings) - now).total_seconds() / 60
    if left <= 0:
        return f"cobrar agora (há {fmt_duration(-left)})", 2
    return f"em {fmt_duration(left)}", 1 if left <= 15 else 0


def deadline_label(t: Ticket, now: datetime) -> tuple[str, int]:
    """Texto da coluna "Prazo" e nivel (0 ok, 1 perto (<1 h), 2 estourado, -1 sem prazo)."""
    if not t.prazo:
        return "—", -1
    left = (t.prazo - now).total_seconds() / 60
    if left <= 0:
        return f"estourado há {fmt_duration(-left)}", 2
    when = t.prazo.strftime("%H:%M") if t.prazo.date() == now.date() else t.prazo.strftime("%d/%m %H:%M")
    return f"{when} (em {fmt_duration(left)})", 1 if left <= 60 else 0
