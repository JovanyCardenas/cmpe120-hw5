#!/usr/bin/env python3
"""CMPE 120 HW5 -- 5-stage pipelined RV32I simulator with BTB and gshare.

Fill in the TODO methods. Everything else -- argument parsing, the run loop,
and all four output writers -- is already written and must not be modified.

HW5 adds a 64-entry direct-mapped BTB and a gshare direction predictor.
BEQ/BNE/JAL/JALR resolve in EX; a wrong predicted next PC flushes ID and IF.
Forwarding and the one-cycle load-use stall carry over from HW4. See the
assignment spec for the BTB/gshare index, tag, and update rules.

Run it with:

    python main.py --iodir <directory containing imem.txt and dmem.txt>
"""

import argparse
import os
import sys

MEM_SIZE = 1000
HALT_INSTR = 0xFFFFFFFF
MASK32 = 0xFFFFFFFF
MAX_CYCLES = 1000000

GSHARE_ENTRIES = 256
GSHARE_INDEX_BITS = 8
GSHARE_INDEX_MASK = GSHARE_ENTRIES - 1
GSHARE_HISTORY_BITS = 8
GSHARE_HISTORY_MASK = (1 << GSHARE_HISTORY_BITS) - 1
GSHARE_INITIAL_COUNTER = 0b10  # weakly taken
GSHARE_TAKEN_THRESHOLD = 0b10

BTB_ENTRIES = 64
BTB_INDEX_BITS = 6
BTB_INDEX_MASK = BTB_ENTRIES - 1


def _stage_pc(stage):
    if stage.get("nop", True):
        return -1
    return int(stage.get("PC", 0)) & MASK32


class GSharePredictor(object):
    """256-entry gshare predictor with 2-bit saturating counters."""

    def __init__(self):
        # TODO: create the counter table and history register.
        # raise NotImplementedError("GSharePredictor.__init__")

        self.counters = [GSHARE_INITIAL_COUNTER] * GSHARE_ENTRIES
        self.history = 0

    def index(self, pc):
        # TODO: return the gshare table index for pc.
        # raise NotImplementedError("GSharePredictor.index")

        # Using provided formula
        return ((pc >> 2) ^ self.history) & GSHARE_INDEX_MASK

    def predict(self, pc):
        # TODO: return (predicted_taken, index) for pc.
        # raise NotImplementedError("GSharePredictor.predict")

        index = self.index(pc)
        predicted_taken = self.counters[index] >= GSHARE_TAKEN_THRESHOLD
        return predicted_taken, index

    def update(self, index, taken):
        # TODO: update the counter at index and the global history.
        # raise NotImplementedError("GSharePredictor.update")

        if taken:
            self.counters[index] = min(3, self.counters[index] + 1)
        else:
            self.counters[index] = max(0, self.counters[index] - 1)

        self.history = ((self.history << 1) | int(taken)) & GSHARE_HISTORY_MASK


class BTB(object):
    """64-entry direct-mapped branch target buffer."""

    def __init__(self):
        # TODO: create the valid, tag, and target arrays.
        # raise NotImplementedError("BTB.__init__")

        self.valid = [False] * BTB_ENTRIES
        self.tags = [0] * BTB_ENTRIES
        self.targets = [0] * BTB_ENTRIES

    def index(self, pc):
        # TODO: return the BTB index for pc.
        # raise NotImplementedError("BTB.index")

        return (pc >> 2) & BTB_INDEX_MASK

    def tag(self, pc):
        # TODO: return the BTB tag for pc.
        # raise NotImplementedError("BTB.tag")

        return (pc >> 8) & 0xFFFFFF

    def lookup(self, pc):
        # TODO: return (hit, target). A miss returns a None target.
        # raise NotImplementedError("BTB.lookup")

        index = self.index(pc)

        if self.valid[index] and self.tags[index] == self.tag(pc):
            return True, self.targets[index]

        return False, None

    def update(self, pc, target):
        # TODO: install pc -> target in the BTB.
        # raise NotImplementedError("BTB.update")

        index = self.index(pc)
        self.valid[index] = True
        self.tags[index] = self.tag(pc)
        self.targets[index] = target & MASK32

class InsMem(object):
    def __init__(self, io_dir):
        with open(os.path.join(io_dir, "imem.txt")) as fh:
            self.bytes = [line.strip() for line in fh if line.strip()]

    def readInstr(self, ReadAddress):
        """Return the 32-bit instruction at byte address ``ReadAddress``.

        The four consecutive bytes are concatenated most-significant byte
        first (big-endian). An address that does not have four bytes of
        instruction memory behind it returns 0.
        """
        if ReadAddress < 0 or ReadAddress + 4 > len(self.bytes):
            return 0
        # TODO: Return the 32-bit instruction at byte address ReadAddress.
        # raise NotImplementedError("InsMem.readInstr")

        """ Turns 4 bytes
                00000000
                00000001
                00000000
                10010011

                into one 32-bit instruction
                00000000000100000000000010010011 
                """

        instruction = "".join(self.bytes[ReadAddress:ReadAddress + 4])
        return int(instruction, 2)


class DataMem(object):
    def __init__(self, io_dir):
        self.io_dir = io_dir
        with open(os.path.join(io_dir, "dmem.txt")) as fh:
            initial = [int(line.strip(), 2) for line in fh if line.strip()]
        self.image = initial + [0] * (MEM_SIZE - len(initial))

    def readDataMem(self, ReadAddress):
        """Read the 32-bit word at byte address ``ReadAddress`` (big-endian).

        Bytes that fall outside the memory read as 0.
        """
        # TODO: Return the 32-bit word at byte address ReadAddress.
        # raise NotImplementedError("DataMem.readDataMem")
        """ Read 4 bytes from memory
                << 8 shifts existing value left by 8 bits
                | byte combines the value with the next byte
                """

        value = 0
        for i in range(4):
            address = ReadAddress + i
            byte = self.image[address] if 0 <= address < MEM_SIZE else 0
            value = (value << 8) | byte

        return value

    def writeDataMem(self, Address, WriteData):
        """Write the low 32 bits of ``WriteData`` at byte address ``Address``.

        Bytes that fall outside the memory are silently dropped.
        """
        # TODO: Store WriteData at byte address Address.
        # raise NotImplementedError("DataMem.writeDataMem")

        # Breaking 32-bit number into four separate bytes
        # & 0xFF extracts one byte at a time

        WriteData = WriteData & MASK32

        for i in range(4):
            address = Address + i
            if 0 <= address < MEM_SIZE:
                shift = 8 * (3 - i)
                self.image[address] = (WriteData >> shift) & 0xFF

    def outputDataMem(self):
        with open(os.path.join(self.io_dir, "DMEMResult.txt"), "w") as fh:
            for byte in self.image:
                fh.write(format(byte, "08b") + "\n")


class RegisterFile(object):
    def __init__(self, io_dir):
        self.io_dir = io_dir
        self.regs = [0] * 32

    def readRF(self, Reg_addr):
        """Return the 32-bit value of register ``Reg_addr``."""
        # TODO: Return the value held in register Reg_addr.
        # raise NotImplementedError("RegisterFile.readRF")

        return self.regs[Reg_addr]

    def writeRF(self, Reg_addr, Wrt_reg_data):
        """Write the low 32 bits of ``Wrt_reg_data`` to register ``Reg_addr``.

        x0 is hardwired to zero, so writes to it are discarded.
        """
        # TODO: Store Wrt_reg_data in register Reg_addr. Writes to x0 are ignored.
        # raise NotImplementedError("RegisterFile.writeRF")

        if Reg_addr != 0:
            self.regs[Reg_addr] = Wrt_reg_data & MASK32

    def outputRF(self):
        with open(os.path.join(self.io_dir, "RFResult.txt"), "w") as fh:
            for value in self.regs:
                fh.write(format(value, "032b") + "\n")


class State(object):
    """Pipeline registers.

    The starter only stores ``nop`` and ``PC`` so the run loop can write the
    trace (``-1`` when ``nop`` is true). Add any other fields your datapath
    needs.
    """

    def __init__(self):
        self.IF = {"nop": False, "PC": 0}
        self.ID = {"nop": True, "PC": 0, "op": ""}
        self.EX = {"nop": True, "PC": 0, "op": ""}
        self.MEM = {"nop": True, "PC": 0, "op": ""}
        self.WB = {"nop": True, "PC": 0}


class Core(object):
    def __init__(self, io_dir, imem, dmem):
        self.io_dir = io_dir
        self.imem = imem
        self.dmem = dmem
        self.myRF = RegisterFile(io_dir)
        self.state = State()
        self.nextState = State()
        self.halted = False
        self.cycle = 0
        self.instructions_executed = 0
        # Update these as control instructions resolve.
        self.conditional_branches = 0
        self.branch_mispredictions = 0
        self.btb_lookups = 0
        self.btb_hits = 0
        self.control_mispredictions = 0
        self.trace = []
        self.verbose = False

    def step(self):
        raise NotImplementedError

    def _pipeline_empty(self):
        return (
            self.state.IF["nop"]
            and self.state.ID["nop"]
            and self.state.EX["nop"]
            and self.state.MEM["nop"]
            and self.state.WB["nop"]
        )

    def run(self):
        while True:
            if self.cycle > 0 and self._pipeline_empty():
                self.halted = True
                break
            if self.cycle >= MAX_CYCLES:
                print("Error: exceeded %d cycles" % MAX_CYCLES, file=sys.stderr)
                self.halted = True
                break
            row = (
                self.cycle,
                _stage_pc(self.state.IF),
                _stage_pc(self.state.ID),
                _stage_pc(self.state.EX),
                _stage_pc(self.state.MEM),
                _stage_pc(self.state.WB),
            )
            self.trace.append(row)
            if self.verbose:
                print(
                    "cycle %-4d IF %-6s ID %-6s EX %-6s MEM %-6s WB %-6s"
                    % row
                )
            self.step()
            self.cycle += 1

        self.myRF.outputRF()
        self.dmem.outputDataMem()
        self.outputTrace()
        self.outputMetrics()

    def outputTrace(self):
        with open(os.path.join(self.io_dir, "TraceResult.txt"), "w") as fh:
            fh.write("# cycle IF.PC ID.PC EX.PC MEM.PC WB.PC\n")
            for row in self.trace:
                fh.write("%d %d %d %d %d %d\n" % row)

    def outputMetrics(self):
        cycles = self.cycle
        executed = self.instructions_executed
        cpi = cycles / executed if executed else 0.0
        ipc = executed / cycles if cycles else 0.0
        branches = self.conditional_branches
        mispredictions = self.branch_mispredictions
        accuracy = (
            100.0 * (branches - mispredictions) / branches
            if branches
            else 100.0
        )
        btb_rate = (
            100.0 * self.btb_hits / self.btb_lookups
            if self.btb_lookups
            else 100.0
        )
        lines = [
            "Total Cycles: %d" % cycles,
            "Instructions Executed: %d" % executed,
            "CPI: %.6f" % cpi,
            "IPC: %.6f" % ipc,
            "Conditional Branches: %d" % branches,
            "Branch Mispredictions: %d" % mispredictions,
            "Branch Prediction Accuracy: %.6f" % accuracy,
            "BTB Lookups: %d" % self.btb_lookups,
            "BTB Hits: %d" % self.btb_hits,
            "BTB Hit Rate: %.6f" % btb_rate,
            "Control Mispredictions: %d" % self.control_mispredictions,
        ]
        with open(os.path.join(self.io_dir, "PerformanceMetrics.txt"), "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n".join(lines))

def sign_extend(value, bits):
    if value & (1 << (bits - 1)):
        return value - (1 << bits)

    return value

def alu(op, a, b):
    if op == "ADD":
        return (a + b) & MASK32
    elif op == "SUB":
        return (a - b) & MASK32
    elif op == "AND":
        return a & b
    elif op == "OR":
        return a | b
    elif op == "XOR":
        return a ^ b

    return 0

def decode(word):
    # Extract instruction fields
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F

    imm = sign_extend(word >> 20, 12)

    alu_ops = {
        0: "ADD",
        4: "XOR",
        6: "OR",
        7: "AND"
    }

    # Decode arithmetic and memory instructions
    if opcode == 0x33:
        if funct3 == 0 and funct7 == 0x20:
            op = "SUB"
        else:
            op = alu_ops[funct3]

    elif opcode == 0x13:
        op = alu_ops[funct3]
        rs2 = None

    elif opcode == 0x03:
        op = "LW"
        rs2 = None

    elif opcode == 0x23:
        op = "SW"
        imm = sign_extend((funct7 << 5) | rd, 12)
        rd = 0

    # Decode Branches and Jumps
    elif opcode == 0x63:
        op = "BEQ" if funct3 == 0 else "BNE"

        imm = sign_extend(
            ((word >> 31) << 12)
            | (((word >> 7) & 1) << 11)
            | (((word >> 25) & 0x3F) << 5)
            | (((word >> 8) & 0xF) << 1),
            13
        )

        rd = 0

    elif opcode == 0x6F:
        op = "JAL"

        imm = sign_extend(
            ((word >> 31) << 20)
            | (((word >> 12) & 0xFF) << 12)
            | (((word >> 20) & 1) << 11)
            | (((word >> 21) & 0x3FF) << 1),
            21
        )

        rs1 = None
        rs2 = None

    elif opcode == 0x67:
        op = "JALR"
        rs2 = None

    else:
        op = "NOP"
        rd = 0
        rs1 = None
        rs2 = None

    return {
        "op": op,
        "rd": rd,
        "rs1": rs1,
        "rs2": rs2,
        "imm": imm
    }

class FiveStageCore(Core):
    """5-stage pipeline with forwarding, load-use stall, BTB, and gshare."""

    def __init__(self, io_dir, imem, dmem):
        super(FiveStageCore, self).__init__(io_dir, imem, dmem)
        self.predictor = GSharePredictor()
        self.btb = BTB()
        self.halt_fetched = False
        # Set by EX when the predicted next PC is wrong.
        self.flush_if_id = False
        self.redirect_pc = None

    def step(self):
        """Advance the pipeline by one clock.

        Process stages backwards (WB -> MEM -> EX -> ID -> IF) so later stages
        see this cycle's results. Write ``self.nextState``, then copy it onto
        ``self.state`` at the end of the clock.

        Count retired instructions in WB. HALT stops fetching; then drain.
        Predict in IF and resolve control instructions in EX.
        """
        # TODO: Implement the 5-stage pipeline, BTB, and gshare for this clock.
        # --------------------- WB stage ---------------------
        # --------------------- MEM stage --------------------
        # --------------------- EX stage ---------------------
        # --------------------- ID stage ---------------------
        # --------------------- IF stage ---------------------
        # raise NotImplementedError("FiveStageCore.step")

        s = self.state # Current pipeline stage
        n = State() # Next clock cycle's state
        self.flush_if_id = False # Whether a control misprediction occurred
        self.redirect_pc = None # stores correct destination after misprediction

        # --------------------- WB stage ---------------------

        if not s.WB["nop"]:
            self.myRF.writeRF(s.WB["rd"], s.WB["result"])
            self.instructions_executed += 1

        # --------------------- MEM stage --------------------

        if not s.MEM["nop"]:
            m = s.MEM
            result = m["result"]

            if m["op"] == "LW":
                result = self.dmem.readDataMem(result)

            elif m["op"] == "SW":
                self.dmem.writeDataMem(result, m["store_data"])

            n.WB = {
                "nop": False,
                "PC": m["PC"],
                "rd": m["rd"],
                "result": result,
            }

        # --------------------- EX stage ---------------------

        if not s.EX["nop"]:
            e = s.EX
            op = e["op"]
            pc = e["PC"]

            def forwarded(reg):
                if reg is None or reg == 0:
                    return 0

                if not s.MEM["nop"] and s.MEM["rd"] == reg:
                    if s.MEM["op"] != "LW":
                        return s.MEM["result"]

                if not s.WB["nop"] and s.WB["rd"] == reg:
                    return s.WB["result"]

                return self.myRF.readRF(reg)

            a = forwarded(e["rs1"])
            b = forwarded(e["rs2"])
            result = 0

            if op in ("LW", "SW"):
                result = (a + e["imm"]) & MASK32
            elif op in ("BEQ", "BNE", "JAL", "JALR"):
                conditional = op in ("BEQ", "BNE")

                if op == "BEQ":
                    taken = a == b
                elif op == "BNE":
                    taken = a != b
                else:
                    taken = True

                actual = pc + 4

                if taken:
                    if op == "JALR":
                        actual = (a + e["imm"]) & ~1
                    else:
                        actual = pc + e["imm"]

                actual &= MASK32

                if conditional:
                    self.conditional_branches += 1

                    if taken != e["predicted_taken"]:
                        self.branch_mispredictions += 1

                    self.predictor.update(
                        e["gshare_index"], taken
                    )

                else:
                    result = (pc + 4) & MASK32

                self.btb_lookups += 1

                if e["btb_hit"]:
                    self.btb_hits += 1
                if taken:
                    self.btb.update(pc, actual)

                if actual != e["predicted_pc"]:
                    self.control_mispredictions += 1
                    self.flush_if_id = True
                    self.redirect_pc = actual

            else:
                operand = e["imm"] if e["rs2"] is None else b
                result = alu(op, a, operand)

            n.MEM = {
                "nop": False,
                "PC": pc,
                "op": op,
                "rd": e["rd"],
                "result": result,
                "store_data": b,
            }

        # --------------------- ID stage ---------------------

        stall = False

        if not self.flush_if_id and not s.ID["nop"]:
            d = s.ID

            if not s.EX["nop"] and s.EX["op"] == "LW":
                if s.EX["rd"] != 0:
                    stall = s.EX["rd"] in (d["rs1"], d["rs2"])

            if stall:
                n.ID = d.copy()
            else:
                n.EX = d.copy()

        # --------------------- IF stage ---------------------

        if self.flush_if_id:
            self.halt_fetched = False
            n.IF = {
                "nop": False,
                "PC": self.redirect_pc
            }

        elif stall:
            n.IF = s.IF.copy()

        elif s.IF["nop"]:
            n.IF = s.IF.copy()

        else:
            pc = s.IF["PC"]
            word = self.imem.readInstr(pc)

            if word == HALT_INSTR or word == 0:
                self.halt_fetched = True
                n.IF = {"nop": True, "PC": pc}

            else:
                d = decode(word)

                predicted_pc = (pc + 4) & MASK32
                predicted_taken = False
                index = None
                hit = False

                # Predict control instructions:
                if d["op"] in ("BEQ", "BNE", "JAL", "JALR"):

                    if d["op"] in ("BEQ", "BNE"):
                        predicted_taken, index = self.predictor.predict(pc)
                    else:
                        predicted_taken = True

                    hit, target = self.btb.lookup(pc)

                    if predicted_taken and hit:
                        predicted_pc = target

                # Pass the instruction to ID
                n.ID = {
                    "nop": False,
                    "PC": pc,
                    **d,
                    "predicted_pc": predicted_pc,
                    "predicted_taken": predicted_taken,
                    "gshare_index": index,
                    "btb_hit": hit
                }

                n.IF = {
                    "nop": False,
                    "PC": predicted_pc
                }
        self.nextState = n
        self.state = n

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="RV32I 5-stage pipelined processor with BTB and gshare"
    )
    parser.add_argument(
        "--iodir",
        default=".",
        type=str,
        help="Directory holding imem.txt and dmem.txt. Outputs are written here.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print one pipeline occupancy line per clock.",
    )
    args = parser.parse_args(argv)

    io_dir = os.path.abspath(args.iodir)
    print("IO Directory:", io_dir)

    core = FiveStageCore(io_dir, InsMem(io_dir), DataMem(io_dir))
    core.verbose = args.verbose
    core.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
