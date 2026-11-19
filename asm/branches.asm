; A branch-predictor demo. Build and run with
; 'python assemble.py branches --run'; expect x1 = 20 and mem[0] = 20.
;
; The BNE is taken 19 times and then not taken once. The first taken
; iteration misses in the BTB; later iterations hit, and the final exit is a
; direction/target misprediction that flushes two instructions. Watch
; PerformanceMetrics.txt for the branch and BTB rates.

ADDI x1, x0, #0              ; count = 0
ADDI x2, x0, #20             ; iterations = 20
loop:
ADDI x1, x1, #1              ; count += 1
ADDI x2, x2, #-1             ; iterations -= 1
BNE  x2, x0, loop            ; back edge: taken 19 times, then not taken
SW   x1, x0, #0              ; mem[0] = 20
HALT
