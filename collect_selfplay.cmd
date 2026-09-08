@echo off
REM ===========================================================================
REM collect_selfplay.cmd - grow the self-play dataset, in one command.
REM
REM Double-click it, or run it from a terminal.  The AI plays itself and writes
REM one row per shot: the position it faced and whether the player about to
REM shoot went on to win.  Nothing is labelled by hand - the game already knows
REM who won.  That file is what a learned position_value() gets trained on.
REM
REM Progress is printed in this window AND appended to the log, so you can see
REM it working either way, and the window stays open when it ends - whether it
REM finished or failed.
REM
REM Rows are appended, and seeds continue past the highest one the file already
REM holds, so running this again always adds new games instead of replaying old
REM ones.  Nothing to edit between runs.  Stopping is safe at any point: Ctrl-C
REM or closing the window keeps every game written so far, minus at most the
REM 100 sitting in the write buffer.
REM
REM   collect_selfplay.cmd            run with the defaults below
REM   collect_selfplay.cmd 8 12 48    hours, workers, candidates per decision
REM ===========================================================================

setlocal
cd /d "%~dp0"

set HOURS=%1
if "%HOURS%"=="" set HOURS=8
set WORKERS=%2
if "%WORKERS%"=="" set WORKERS=12
set CANDIDATES=%3
if "%CANDIDATES%"=="" set CANDIDATES=48

set OUT=selfplay.jsonl
set LOG=selfplay.log

python -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python was not found on PATH, so nothing can run here.
    echo Open a terminal, check that "python -V" answers, then try again.
    echo.
    pause
    exit /b 1
)

echo.
echo Collecting for %HOURS% h on %WORKERS% workers, %CANDIDATES% candidates per decision.
echo Rows are appended to %OUT%, progress also goes to %LOG%.
echo The first progress line lands after 100 games, so give it a few minutes.
echo.

REM -u so this window updates as it goes instead of holding output in a buffer.
python -u -m ai.selfplay ^
    --policy ai_policy.json ^
    --out %OUT% ^
    --log %LOG% ^
    --append ^
    --games 100000 ^
    --max-hours %HOURS% ^
    --candidates %CANDIDATES% ^
    --workers %WORKERS% ^
    --seed-start auto ^
    --report-every 100

echo.
echo Done.  The dataset is %OUT%, the run is logged in %LOG%.
pause
endlocal
