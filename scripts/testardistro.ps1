$origem = "C:\Users\a958054\Projects\base-de-conhecimento-semantix\dist\BaseConhecimento"

$destino = "C:\Users\a958054\Projects\dist"

try {

        Copy-Item -Path $origem -Destination $destino -Recurse -Force
        Write-Host "Copiado"

}
Catch {
    Write-Host "Erro: $($_.Exception.Message)" - ForegroundColor Red
}