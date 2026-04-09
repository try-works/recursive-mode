@echo off
REM Optional template — NOT auto-installed by Skills CLI.
REM If your agent/runtime supports hooks, you may wire this up manually.
REM
REM Hook Runner for Windows
REM Usage: run-hook.cmd <hook-name> [args...]

setlocal EnableDelayedExpansion

set "HOOK_NAME=%~1"
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

if "%HOOK_NAME%"=="" (
    echo Error: No hook name specified
    echo Usage: run-hook.cmd ^<hook-name^>
    exit /b 1
)

if "%HOOK_NAME%"=="session-start" (
    if exist "%SCRIPT_DIR%session-start.sh" (
        REM Try bash first (Git Bash, WSL, Cygwin)
        where bash >nul 2>&1
        if !errorlevel! equ 0 (
            bash "%SCRIPT_DIR%session-start.sh" %*
            exit /b !errorlevel!
        )

        REM Try sh
        where sh >nul 2>&1
        if !errorlevel! equ 0 (
            sh "%SCRIPT_DIR%session-start.sh" %*
            exit /b !errorlevel!
        )

        REM Fall back to PowerShell
        if exist "%SCRIPT_DIR%session-start.ps1" (
            powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%session-start.ps1" %*
            exit /b !errorlevel!
        )

        echo Warning: Could not find bash, sh, or PowerShell to run hook
        exit /b 0
    )
)

echo Unknown hook: %HOOK_NAME%
exit /b 1
