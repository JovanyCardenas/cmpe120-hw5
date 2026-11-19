; PC   ENCODING     INSTRUCTION

0      0x00000093   ADDI R1, R0, #0
4      0x00C00113   ADDI R2, R0, #12
8      0x00117193   ANDI R3, R2, #1
12     0x00018663   BEQ R3, R0, #12
16     0x002080B3   ADD R1, R1, R2
20     0x0080006F   JAL R0, #8
24     0x402080B3   SUB R1, R1, R2
28     0xFFF10113   ADDI R2, R2, #-1
32     0xFE0114E3   BNE R2, R0, #-24
36     0x00102023   SW R1, #0(R0)
40     0xFFFFFFFF   HALT

labels:
  outer            8
  even             24
  next             28
