; PC   ENCODING     INSTRUCTION

0      0x00000093   ADDI R1, R0, #0
4      0x00000113   ADDI R2, R0, #0
8      0x00400193   ADDI R3, R0, #4
12     0x00000393   ADDI R7, R0, #0
16     0x014002EF   JAL R5, #20
20     0x00110113   ADDI R2, R2, #1
24     0xFE311CE3   BNE R2, R3, #-8
28     0x00702023   SW R7, #0(R0)
32     0xFFFFFFFF   HALT
36     0x00108093   ADDI R1, R1, #1
40     0x0010F313   ANDI R6, R1, #1
44     0x00030663   BEQ R6, R0, #12
48     0x00338393   ADDI R7, R7, #3
52     0x0080006F   JAL R0, #8
56     0x00138393   ADDI R7, R7, #1
60     0x00028067   JALR R0, R5, #0

labels:
  call_loop        16
  func             36
  even_call        56
  ret              60
