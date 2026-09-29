[CmdletBinding()]
param(
    [ValidateSet('public','github','sheet')][string]$Task = 'public',
    [string]$SimulationDir,
    [string]$RequirementsDir,
    [string]$RunsDir,
    [switch]$BuildImage,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Simulation = if ($SimulationDir) { [System.IO.Path]::GetFullPath($SimulationDir) } else { Join-Path $ProjectRoot 'work\hackathon-local-simulation' }
$Config = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $Config)) { throw 'Missing local .env configuration.' }
if (-not (Test-Path -LiteralPath (Join-Path $Simulation 'local_submit.py'))) {
    throw 'The official simulator checkout is missing.'
}
$DockerCandidates = @(
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin",
    "$env:ProgramFiles\Docker\Docker\resources\bin"
)
foreach ($Directory in $DockerCandidates) {
    if (Test-Path -LiteralPath (Join-Path $Directory 'docker.exe')) {
        $env:PATH = "$Directory;$env:PATH"
        break
    }
}
if (-not $PrepareOnly) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Install and start Docker Desktop with Linux containers, then run this script again.'
    }
    $Engine = & docker info --format '{{.OSType}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or $Engine -ne 'linux') {
        throw 'Docker Linux engine is not ready. Finish Desktop setup and any required Windows restart.'
    }
    if ($BuildImage) {
        & (Join-Path $Simulation 'build-image.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Official Runner image build failed.' }
    }
    & docker image inspect arcbench-local-submit:latest *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Runner image missing. Run this script with -BuildImage.' }
}
& python (Join-Path $PSScriptRoot 'package_agent.py')
if ($LASTEXITCODE -ne 0) { throw 'Agent packaging failed.' }
$Tests = $null
switch ($Task) {
    'public' {
        $Requirements = Join-Path $Simulation 'public-exercise\keep\requirements'
        $Tests = Join-Path $Simulation 'public-exercise\keep\tests'
        $TaskId = 'keep'
    }
    'github' {
        $Requirements = Join-Path $ProjectRoot 'outputs\arcbench-v0\requirements\hackathon--github'
        $TaskId = 'hackathon--github'
    }
    'sheet' {
        $Requirements = Join-Path $ProjectRoot 'outputs\arcbench-v0\requirements\hackathon--sheet'
        $TaskId = 'hackathon--sheet'
    }
}
# Only public requirement input is passed; never pass the sibling demo application as a template.
if ($RequirementsDir) { $Requirements = [System.IO.Path]::GetFullPath($RequirementsDir) }
if (-not (Test-Path -LiteralPath (Join-Path $Requirements 'requirements.yaml'))) {
    throw 'Requirements directory missing. Supply -RequirementsDir pointing to the public task download.'
}
$RunId = '{0}-{1}-{2}' -f $Task, (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N').Substring(0,6))
$RunDirectory = if ($RunsDir) { Join-Path ([System.IO.Path]::GetFullPath($RunsDir)) $RunId } else { Join-Path $ProjectRoot "work\runs\$RunId" }
$Arguments = @((Join-Path $Simulation 'local_submit.py'), 'run',
    '--agent', (Join-Path $ProjectRoot 'outputs\arcbench-agent.zip'),
    '--requirements-dir', $Requirements, '--output-dir', $RunDirectory,
    '--env-file', $Config, '--task', $TaskId, '--competition', 'local-practice',
    '--memory', '2g', '--cpus', '1')
if ($Tests) { $Arguments += @('--tests-dir', $Tests) }
if ($PrepareOnly) { $Arguments += '--prepare-only' }
Write-Host "Run output: $RunDirectory"
& python @Arguments
if ($LASTEXITCODE -ne 0) { throw "Local run failed; inspect $RunDirectory\execution.debug.log" }
