"""
Gera os stubs gRPC a partir dos arquivos .proto em proto/ e corrige
os imports relativos gerados pelo protoc para imports absolutos.

Referência: https://grpc.io/docs/languages/python/quickstart/
"""

import pathlib
import re
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTO_DIR = PROJECT_ROOT / "proto"
OUT_DIR = PROJECT_ROOT / "app" / "clients" / "generated"

# ── Validações ────────────────────────────────────────────────────────────

proto_files = list(PROTO_DIR.glob("*.proto"))
if not proto_files:
    print(f"Erro: nenhum arquivo .proto encontrado em {PROTO_DIR}")
    sys.exit(1)

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Geração dos stubs ─────────────────────────────────────────────────────

cmd = [
    sys.executable, "-m", "grpc_tools.protoc",
    f"--proto_path={PROTO_DIR}",
    f"--python_out={OUT_DIR}",
    f"--grpc_python_out={OUT_DIR}",
    *[str(f) for f in proto_files],
]

print("Gerando stubs...")
result = subprocess.run(cmd)
if result.returncode != 0:
    print("Erro na geração dos stubs.")
    sys.exit(result.returncode)

# ── Correção de imports ───────────────────────────────────────────────────
# O protoc gera "import user_pb2 as user__pb2" nos arquivos *_pb2_grpc.py.
# Em Python 3 todos os imports são absolutos, então isso falha.
# Corrige para "from app.clients.generated import user_pb2 as user__pb2".

for f in OUT_DIR.glob("*_pb2_grpc.py"):
    txt = f.read_text(encoding="utf-8")
    txt = re.sub(
        r"^import (\w+_pb2)",
        r"from app.clients.generated import \1",
        txt,
        flags=re.MULTILINE,
    )
    f.write_text(txt, encoding="utf-8")

# ── Resultado ─────────────────────────────────────────────────────────────

generated = sorted(OUT_DIR.glob("*.py"))
print(f"\nStubs gerados em {OUT_DIR.relative_to(PROJECT_ROOT)}/")
for f in generated:
    print(f"  {f.name}")