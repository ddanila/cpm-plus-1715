; MIT. CRC-16/IBM reflected polynomial A001h, split low/high pages.
; Entry n is eight right-shift/XOR steps from n. Tested against bitwise CRC.
        ds (-$) & 255,0
N3CRCLO:
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 001h,0c0h,080h,041h,000h,0c1h,081h,040h,000h,0c1h,081h,040h,001h,0c0h,080h,041h
        db 000h,0c1h,081h,040h,001h,0c0h,080h,041h,001h,0c0h,080h,041h,000h,0c1h,081h,040h
N3CRCHI:
        db 000h,0c0h,0c1h,001h,0c3h,003h,002h,0c2h,0c6h,006h,007h,0c7h,005h,0c5h,0c4h,004h
        db 0cch,00ch,00dh,0cdh,00fh,0cfh,0ceh,00eh,00ah,0cah,0cbh,00bh,0c9h,009h,008h,0c8h
        db 0d8h,018h,019h,0d9h,01bh,0dbh,0dah,01ah,01eh,0deh,0dfh,01fh,0ddh,01dh,01ch,0dch
        db 014h,0d4h,0d5h,015h,0d7h,017h,016h,0d6h,0d2h,012h,013h,0d3h,011h,0d1h,0d0h,010h
        db 0f0h,030h,031h,0f1h,033h,0f3h,0f2h,032h,036h,0f6h,0f7h,037h,0f5h,035h,034h,0f4h
        db 03ch,0fch,0fdh,03dh,0ffh,03fh,03eh,0feh,0fah,03ah,03bh,0fbh,039h,0f9h,0f8h,038h
        db 028h,0e8h,0e9h,029h,0ebh,02bh,02ah,0eah,0eeh,02eh,02fh,0efh,02dh,0edh,0ech,02ch
        db 0e4h,024h,025h,0e5h,027h,0e7h,0e6h,026h,022h,0e2h,0e3h,023h,0e1h,021h,020h,0e0h
        db 0a0h,060h,061h,0a1h,063h,0a3h,0a2h,062h,066h,0a6h,0a7h,067h,0a5h,065h,064h,0a4h
        db 06ch,0ach,0adh,06dh,0afh,06fh,06eh,0aeh,0aah,06ah,06bh,0abh,069h,0a9h,0a8h,068h
        db 078h,0b8h,0b9h,079h,0bbh,07bh,07ah,0bah,0beh,07eh,07fh,0bfh,07dh,0bdh,0bch,07ch
        db 0b4h,074h,075h,0b5h,077h,0b7h,0b6h,076h,072h,0b2h,0b3h,073h,0b1h,071h,070h,0b0h
        db 050h,090h,091h,051h,093h,053h,052h,092h,096h,056h,057h,097h,055h,095h,094h,054h
        db 09ch,05ch,05dh,09dh,05fh,09fh,09eh,05eh,05ah,09ah,09bh,05bh,099h,059h,058h,098h
        db 088h,048h,049h,089h,04bh,08bh,08ah,04ah,04eh,08eh,08fh,04fh,08dh,04dh,04ch,08ch
        db 044h,084h,085h,045h,087h,047h,046h,086h,082h,042h,043h,083h,041h,081h,080h,040h
