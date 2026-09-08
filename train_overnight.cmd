@echo off
REM ===========================================================================
REM train_overnight.cmd - a night of policy training, in one command.
REM
REM Every mutation and the champion play the same games on the same seeds, so
REM a generation is decided by the policies rather than by the tables they drew.
REM Matches are independent, so they are spread over WORKERS processes and the
REM wall clock divides by that.
REM
REM The champion is written to OUTPUT every time it improves, so stopping the
REM run at any point (Ctrl-C, or closing the window) keeps the best policy
REM found so far.  The current ai_policy.json is never touched.
REM
REM   train_overnight.cmd            run with the defaults below
REM   train_overnight.cmd 10 12 48   hours, workers, candidates per decision
REM ===========================================================================

setlocal
cd /d "%~dp0"

set HOURS=%1
if "%HOURS%"=="" set HOURS=10
set WORKERS=%2
if "%WORKERS%"=="" set WORKERS=12
set CANDIDATES=%3
if "%CANDIDATES%"=="" set CANDIDATES=48

set OUTPUT=ai_policy_night.json
set LOG=train_overnight.log

echo Training for %HOURS% h on %WORKERS% workers, %CANDIDATES% candidates per decision.
echo Champion goes to %OUTPUT%, progress to %LOG%.

REM -u so the log is written as it goes, not held in a buffer all night.
python -u -m ai.train ^
    --input ai_policy.json ^
    --opponent ai_policy.json ^
    --output %OUTPUT% ^
    --generations 100000 ^
    --max-hours %HOURS% ^
    --population 6 ^
    --episodes 10 ^
    --candidates %CANDIDATES% ^
    --workers %WORKERS% ^
    --promote 0.75 ^
    --mutation-scale 0.15 > %LOG% 2>&1

echo Done.  See %LOG% for the run and %OUTPUT% for the policy.
endlocal
