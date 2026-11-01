@echo off
setlocal
chcp 949 >nul
cd /d "%~dp0"
title 스마트PDF Editor - 실행파일 만들기

echo ==================================================
echo   스마트PDF Editor  실행파일(exe) 만들기
echo ==================================================
echo.

if not exist "smartpdfeditor.py" (
    echo [오류] smartpdfeditor.py 가 이 폴더에 없습니다.
    echo        배치파일과 같은 폴더에 넣고 다시 실행해주세요.
    goto :fail
)

rem ---- 파이썬 찾기 (py 런처 우선) ----
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [오류] 파이썬을 찾을 수 없습니다.
    echo        https://www.python.org 에서 설치하고,
    echo        설치 첫 화면의 "Add python.exe to PATH" 를 꼭 체크해주세요.
    goto :fail
)
for /f "delims=" %%v in ('%PY% --version') do echo [1/4] %%v 확인
echo.

rem ---- 필요한 프로그램 설치 ----
echo [2/4] 필요한 프로그램 설치 중 (PyMuPDF, PyInstaller)...
set "LOG=%~dp0설치오류_기록.txt"
if exist "%LOG%" del /q "%LOG%" >nul 2>&1

rem pip 가 없으면 먼저 설치
%PY% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo     pip 가 없어 설치합니다...
    %PY% -m ensurepip --upgrade >>"%LOG%" 2>&1
)

rem 64/32비트 확인
for /f "delims=" %%b in ('%PY% -c "import struct;print(struct.calcsize('P')*8)"') do set "BITS=%%b"
echo     파이썬 %BITS%비트

rem --only-binary : 소스 빌드(컴파일러 필요)를 하지 않고, 완성본(wheel)이 있는 버전만 설치
set "BIN=--only-binary=:all: --prefer-binary"
set "HOSTS=--trusted-host pypi.org --trusted-host files.pythonhosted.org"

echo     방법 1: 완성본으로 설치 (PyMuPDF 1.x)
%PY% -m pip install --upgrade %BIN% "pymupdf<2" pyinstaller >>"%LOG%" 2>&1
if not errorlevel 1 goto :installed

echo     방법 2: 검증된 이전 버전(PyMuPDF 1.x)으로 설치
%PY% -m pip install --upgrade %BIN% "pymupdf<2" pyinstaller >>"%LOG%" 2>&1
if not errorlevel 1 goto :installed

echo     방법 3: 사용자 폴더에 설치 (권한 문제 대비)
%PY% -m pip install --user --upgrade %BIN% "pymupdf<2" pyinstaller >>"%LOG%" 2>&1
if not errorlevel 1 goto :installed

echo     방법 4: 보안 인증서 검사 우회 (회사/기관 보안망 대비)
%PY% -m pip install --user --upgrade %BIN% %HOSTS% "pymupdf<2" pyinstaller >>"%LOG%" 2>&1
if not errorlevel 1 goto :installed

echo.
echo [오류] 설치에 실패했습니다.
echo   - 오류 내용이 "설치오류_기록.txt" 에 저장됐습니다.
echo     이 파일의 마지막 부분을 알려주시면 원인을 찾을 수 있습니다.
echo.
findstr /i /c:"SSL" /c:"CERTIFICATE" "%LOG%" >nul 2>&1 && echo   * 보안망에서 인터넷 연결이 막힌 것 같습니다. 집이나 다른 인터넷에서 해보세요.
findstr /i /c:"getaddrinfo" /c:"connection" /c:"timed out" /c:"ProxyError" "%LOG%" >nul 2>&1 && echo   * 인터넷 연결 문제입니다. 프록시/방화벽을 확인해주세요.
findstr /i /c:"Permission" /c:"Access is denied" /c:"액세스가 거부" "%LOG%" >nul 2>&1 && echo   * 권한 문제입니다. 배치파일을 우클릭해 "관리자 권한으로 실행" 해보세요.
findstr /i /c:"No matching distribution" /c:"nmake" /c:"Failed to build" "%LOG%" >nul 2>&1 && echo   * 이 파이썬에 맞는 PyMuPDF 완성본이 없습니다. 64비트 Python 3.12 를 설치해주세요.
if "%BITS%"=="32" echo   * 지금 파이썬이 32비트입니다. 64비트 Python 3.12 를 설치해주세요.
start "" notepad "%LOG%"
goto :fail

:installed
echo     설치 완료
%PY% -c "import fitz, PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [오류] 설치는 됐지만 불러올 수 없습니다. 64비트 Python 3.12 설치를 권장합니다.
    goto :fail
)
echo.

rem ---- 아이콘 (같은 폴더에 app.ico 가 있으면 사용) ----
set "ICON="
if exist "smartpdfeditor.ico" set "ICON=--icon smartpdfeditor.ico"
rem 탐색기 파일 속성·'연결 프로그램' 목록에 보일 이름과 버전 (스마트PDF Editor 1.0.0)
set "VERF="
if exist "tools\make_version_info.py" (
    %PY% tools\make_version_info.py >nul 2>&1
    if exist "version_info.txt" set "VERF=--version-file version_info.txt"
)

rem ---- 실행파일 만들기 ----
echo [3/4] 실행파일 만드는 중... (1~3분 걸립니다)
if exist "smartpdfeditor.exe" del /q "smartpdfeditor.exe" >nul 2>&1
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name smartpdfeditor %ICON% %VERF% ^
    --collect-all pymupdf ^
    smartpdfeditor.py
if errorlevel 1 (
    echo [오류] 실행파일 만들기에 실패했습니다. 위 메시지를 확인해주세요.
    goto :fail
)
echo.

rem ---- 정리 ----
echo [4/4] 정리 중...
copy /y "dist\smartpdfeditor.exe" "smartpdfeditor.exe" >nul
rmdir /s /q build >nul 2>&1
rmdir /s /q dist >nul 2>&1
del /q smartpdfeditor.spec >nul 2>&1

echo.
echo ==================================================
echo   완료!  smartpdfeditor.exe 가 만들어졌습니다.
echo   위치: %~dp0smartpdfeditor.exe
echo ==================================================
echo.
choice /c YN /n /m "지금 실행해볼까요? (Y/N) "
if errorlevel 2 goto :end
start "" "smartpdfeditor.exe"
goto :end

:fail
echo.
echo 실패했습니다. 아무 키나 누르면 닫힙니다.
pause >nul
exit /b 1

:end
endlocal
exit /b 0
