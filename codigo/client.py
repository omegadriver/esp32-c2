import subprocess
import serial
import json
import uuid
import base64
import time
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

DEVICE_ID   = "b7d412b0-6953-45a9-8bab-680796f8e927"
DEVICE_NAME = "OMEGADRIVER"
ACCOUNT     = "hairy"
PORT        = "COM5"
BAUD        = 115200

# ── log ───────────────────────────────────────────────────────────────

RESET  = "\033[0m"
GRAY   = "\033[90m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"

def ts():
    return time.strftime("%H:%M:%S")

def log(who, color, msg):
    print(f"{GRAY}{ts()}{RESET}  {color}{BOLD}[{who}]{RESET}  {msg}")

def log_client(msg):   log("client", CYAN,   msg)
def log_esp32(msg):    log("esp32",  YELLOW, msg)
def log_error(msg):    log("erro",   RED,    msg)


# ── FSM ───────────────────────────────────────────────────────────────

class Phase(Enum):
    WAIT_COMMAND    = auto()
    EXECUTE_COMMAND = auto()
    FORMAT_RESULT   = auto()
    SEND_RESULT     = auto()


@dataclass
class Context:
    raw_message:    Optional[dict]  = None
    command:        Optional[str]   = None
    stdout:         bytes           = b""
    stderr:         bytes           = b""
    exit_code:      int             = 0
    execution_ms:   int             = 0
    result_json:    Optional[bytes] = None
    correlation_id: Optional[str]   = None


# ── handlers ──────────────────────────────────────────────────────────

def wait_command(ctx: Context, ser: serial.Serial) -> Phase:
    time.sleep(1)
    line = ser.readline()
    if not line:
        return Phase.WAIT_COMMAND

    if line.startswith(b"[esp32]"):
        log_esp32(line.decode("utf-8", errors="ignore").strip().removeprefix("[esp32]").strip())
        return Phase.WAIT_COMMAND

    try:
        msg = json.loads(line.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return Phase.WAIT_COMMAND

    if not isinstance(msg, dict):
        return Phase.WAIT_COMMAND

    if msg.get("type") != "command":
        return Phase.WAIT_COMMAND

    try:
        ctx.raw_message    = msg
        ctx.command        = msg["payload"]["command"]
        ctx.correlation_id = msg.get("messageid")
    except KeyError as e:
        log_error(f"campo ausente no comando → {e}")
        return Phase.WAIT_COMMAND

    log_client(f"comando recebido → {BOLD}{ctx.command}{RESET}")
    return Phase.EXECUTE_COMMAND

def execute_command(ctx: Context) -> Phase:
    timeout = ctx.raw_message["payload"].get("timeoutms", 5000) / 1000
    cwd     = ctx.raw_message["payload"].get("workingdirectory")

    log_client(f"executando → {ctx.command}")

    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            ctx.command,
            shell=True,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
        ctx.stdout = proc.stdout.decode("cp850", errors="replace").encode("utf-8")
        ctx.stderr = proc.stderr.decode("cp850", errors="replace").encode("utf-8")
        ctx.execution_ms = int((time.monotonic() - t0) * 1000)
        ctx.exit_code    = proc.returncode

        status = f"{GREEN}exit {ctx.exit_code}{RESET}" if ctx.exit_code == 0 else f"{RED}exit {ctx.exit_code}{RESET}"
        log_client(f"execução de comando concluída {status}  {GRAY}{ctx.execution_ms}ms{RESET}")
        return Phase.FORMAT_RESULT

    except subprocess.TimeoutExpired:
        log_error(f"timeout ao executar → {ctx.command}")
        ctx.stderr    = b"timeout"
        ctx.exit_code = -1
        return Phase.FORMAT_RESULT

    except Exception as e:
        log_error(f"falha ao executar → {e}")
        ctx.stderr    = str(e).encode()
        ctx.exit_code = -2
        return Phase.FORMAT_RESULT


def format_result(ctx: Context, device_id: str, device_name: str, account: str) -> Phase:
    stdout_b64 = base64.b64encode(ctx.stdout).decode()
    stderr_b64 = base64.b64encode(ctx.stderr).decode()

    payload = {
        "command":     ctx.command,
        "exitcode":    ctx.exit_code,
        "payloadsize": len(stdout_b64),
        "stdout":      stdout_b64,
        "stderr":      stderr_b64,
        "executionms": ctx.execution_ms,
    }

    msg = {
        "messageid":     str(uuid.uuid4()),
        "correlationid": ctx.correlation_id,
        "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type":          "command_result",
        "direction":     "client→server",
        "deviceid":      device_id,
        "devicename":    device_name,
        "accountname":   account,
        "encoding":      "base64",
        "payload":       payload,
    }

    ctx.result_json = (json.dumps(msg) + "\n").encode("utf-8")
    log_client(f"resultado formatado  {GRAY}{len(ctx.result_json)} bytes{RESET}")
    return Phase.SEND_RESULT


def send_result(ctx: Context, ser: serial.Serial) -> Phase:
    ser.write(ctx.result_json)
    ser.flush()
    log_client(f"resultado enviado ao ESP32 via serial")

    ctx.raw_message    = None
    ctx.command        = None
    ctx.stdout         = b""
    ctx.stderr         = b""
    ctx.exit_code      = 0
    ctx.execution_ms   = 0
    ctx.result_json    = None
    ctx.correlation_id = None

    return Phase.WAIT_COMMAND


# ── main ──────────────────────────────────────────────────────────────

def main():
    log_client("inicializando...")
    time.sleep(2)
    log_client(f"abrindo porta {PORT} @ {BAUD} baud")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        log_client(f"porta {PORT} aberta")

    except serial.SerialException as e:
        if "already in use" in str(e).lower() or "access denied" in str(e).lower():
            log_error(f"porta {PORT} já está em uso ou sem permissão")
        else:
            log_error(f"não foi possível abrir {PORT} → {e}")
        return
    except Exception as e:
        log_error(f"erro inesperado → {e}")
        return

    ctx   = Context()
    phase = Phase.WAIT_COMMAND

    while True:
        match phase:
            case Phase.WAIT_COMMAND:
                phase = wait_command(ctx, ser)
            case Phase.EXECUTE_COMMAND:
                phase = execute_command(ctx)
            case Phase.FORMAT_RESULT:
                phase = format_result(ctx, DEVICE_ID, DEVICE_NAME, ACCOUNT)
            case Phase.SEND_RESULT:
                phase = send_result(ctx, ser)


if __name__ == "__main__":
    main()
