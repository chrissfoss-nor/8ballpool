@echo off
REM ===========================================================================
REM collect_selfplay.cmd - grow the self-play dataset, in one command.
REM
REM The AI plays itself and writes one row per shot: the position it faced and
REM whether the player about to shoot went on to win.  Nothing is labelled by
REM hand - the game already knows who won.  That file is what a learned
REM position_value() gets trained on.
REM
REM Rows are APPENDED, so running this again adds to what is already there.
REM Every run must use a fresh SEEDSTART, or it replays games the file already
REM holds - so edit SEEDSTART below before each run.  The script reminds you
REM when it finishes; it cannot edit itself.
REM
REM Stopping is safe at any point: Ctrl-C or closing the window keeps every
REM game written so far.  Up to 100 games sitting in the write buffer are lost,
REM nothing else.
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

REM Seeds already used: 100000-102660.  Bump this by 100000 before each run.
set SEEDSTART=200000

set OUT=selfplay.jsonl
set LOG=selfplay.log

echo Collecting for %HOURS% h on %WORKERS% workers, %CANDIDATES% candidates per decision.
echo Seeds from %SEEDSTART%.  Rows are appended to %OUT%, progress to %LOG%.

REM -u so the log is written as it goes, not held in a buffer all night.
python -u -m ai.selfplay ^
    --policy ai_policy.json ^
    --out %OUT% ^
    --append ^
    --games 100000 ^
    --max-hours %HOURS% ^
    --candidates %CANDIDATES% ^
    --workers %WORKERS% ^
    --seed-start %SEEDSTART% ^
    --report-every 100 > %LOG% 2>&1

echo Done.  See %LOG% for the run and %OUT% for the dataset.
echo Remember to bump SEEDSTART in this file before the next run.
endlocal
