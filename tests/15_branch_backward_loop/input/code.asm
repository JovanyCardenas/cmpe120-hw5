; PC   ENCODING     INSTRUCTION

0      0x00000093   ADDI R1, R0, #0
4      0x00500113   ADDI R2, R0, #5
8      0x002080B3   ADD R1, R1, R2
12     0xFFF10113   ADDI R2, R2, #-1
16     0xFE011CE3   BNE R2, R0, #-8
20     0x00102023   SW R1, #0(R0)
24     0xFFFFFFFF   HALT

labels:
  loop             8
