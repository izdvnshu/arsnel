# ARSNEL installer for Windows (PowerShell 5.1 or 7). Installs into ~\.arsnel, no admin rights.
# Safe to run as a script block: it uses throw and never calls exit, and its variables stay local.
# Options (environment variables):
#   ARSNEL_REF=main          branch, tag or commit to install (pin a tag for repeatable installs)
#   ARSNEL_REPO=<https url>  repository to install from
#   ARSNEL_MODEL=llama3.2    model to pull with ollama
#   ARSNEL_SKIP_MODEL=1      do not pull a model
#   ARSNEL_DRY_RUN=1         print what would happen and change nothing
& {
    $ErrorActionPreference = 'Stop'

    $Repo  = if ($env:ARSNEL_REPO)  { $env:ARSNEL_REPO }  else { 'https://github.com/YOUR_USERNAME/arsnel.git' }
    $Ref   = if ($env:ARSNEL_REF)   { $env:ARSNEL_REF }   else { 'main' }
    $Model = if ($env:ARSNEL_MODEL) { $env:ARSNEL_MODEL } else { 'llama3.2' }
    $Root  = if ($env:ARSNEL_HOME)  { $env:ARSNEL_HOME }  else { Join-Path $env:USERPROFILE '.arsnel' }
    $Dry   = $env:ARSNEL_DRY_RUN -eq '1'
    $Venv  = Join-Path $Root 'venv'
    $BinDir = Join-Path $Root 'bin'

    function Invoke-Step([string]$Exe, [string[]]$ArgList) {
        if ($Dry) { Write-Host "[dry-run] $Exe $($ArgList -join ' ')"; return }
        & $Exe @ArgList
        if ($LASTEXITCODE -ne 0) { throw "'$Exe $($ArgList -join ' ')' failed (exit code $LASTEXITCODE)." }
    }

    if ($Repo -like '*YOUR_USERNAME*') { throw 'Replace YOUR_USERNAME with your GitHub username (or set ARSNEL_REPO).' }
    if ($Repo -notmatch '^(https://|file://)') { throw "ARSNEL_REPO must start with https:// (got: $Repo)" }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'git is required. Install it from https://git-scm.com/downloads'
    }

    $py = $null
    foreach ($candidate in @(@('py', '-3.12'), @('py', '-3.11'), @('python'), @('python3'))) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $extra = @($candidate | Select-Object -Skip 1)
        try {
            & $exe @extra -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { $py = $candidate; break }
        } catch { continue }
    }
    if (-not $py) { throw 'Python 3.11 or newer is required. Install it from https://www.python.org/downloads/' }

    Write-Host "Installing ARSNEL ($Ref) into $Root using $($py -join ' ')"
    if (-not $Dry) { New-Item -ItemType Directory -Force -Path $Root, $BinDir | Out-Null }
    Invoke-Step $py[0] (@($py | Select-Object -Skip 1) + @('-m', 'venv', $Venv))
    $venvPy = Join-Path $Venv 'Scripts\python.exe'
    Invoke-Step $venvPy @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip')
    Invoke-Step $venvPy @('-m', 'pip', 'install', '--quiet', "git+$Repo@$Ref")

    # A tiny launcher so `arsnel` works without activating the virtual environment.
    $shim = Join-Path $BinDir 'arsnel.cmd'
    if (-not $Dry) {
        Set-Content -Path $shim -Encoding Ascii -Value ('@"{0}" %*' -f (Join-Path $Venv 'Scripts\arsnel.exe'))
    }

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @(([string]$userPath) -split ';' | Where-Object { $_ })
    if ($entries -notcontains $BinDir) {
        if (-not $Dry) {
            [Environment]::SetEnvironmentVariable('Path', (($entries + $BinDir) -join ';'), 'User')
            $env:Path = "$env:Path;$BinDir"
        }
        Write-Host "Added $BinDir to your user PATH."
    }

    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        if ($env:ARSNEL_SKIP_MODEL -eq '1') { Write-Host 'Skipping model download.' }
        else { Invoke-Step 'ollama' @('pull', $Model) }
    } else {
        Write-Host "ollama is not installed. Get it from https://ollama.com, then run: ollama pull $Model"
    }

    Write-Host 'Done. Try: arsnel --help'
}
