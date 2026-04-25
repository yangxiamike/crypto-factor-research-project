@echo off
cd /d C:\Users\hp\work\crypto-factor-research-project
echo [%date% %time%] starting UI > C:\Users\hp\work\crypto-factor-research-project\.tmp\cmd-ui.log
"C:\Users\hp\anaconda3\python.exe" "C:\Users\hp\work\crypto-factor-research-project\scripts\start_ui.py" >> C:\Users\hp\work\crypto-factor-research-project\.tmp\cmd-ui.log 2>&1
echo [%date% %time%] UI exited with %ERRORLEVEL% >> C:\Users\hp\work\crypto-factor-research-project\.tmp\cmd-ui.log
