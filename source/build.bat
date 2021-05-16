@echo off
pyinstaller TheForgottenLands.py -n "The Forgotten Lands" -w -F -y --distpath ..\bin --workpath .\temp --specpath .\temp -i ..\data\images\icons\icon16x16.ico -i ..\data\images\icons\icon32x32.ico -i ..\data\images\icons\icon48x48.ico -i ..\data\images\icons\icon64x64.ico -i ..\data\images\icons\icon128x128.ico --add-data ..\data;.\data --exclude-module numpy --exclude-module win32com --exclude-module pygame
rmdir /S /Q .\temp
rmdir /S /Q .\__pycache__