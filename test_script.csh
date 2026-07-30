echo Hello!
:start
echo Please enter text:
set "in=%input%"
goto eof %in% exit
echo You entered: %in%
goto start
:eof
quit
