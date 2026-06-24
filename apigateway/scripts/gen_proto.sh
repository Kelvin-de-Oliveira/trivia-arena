#!/usr/bin/env bash
# Gera os stubs Python a partir dos arquivos .proto em proto/
# Uso: bash scripts/gen_proto.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$PROJECT_ROOT/proto"
OUT_DIR="$PROJECT_ROOT/generated"

if [ ! -d "$PROTO_DIR" ] || [ -z "$(ls "$PROTO_DIR"/*.proto 2>/dev/null)" ]; then
    echo "Erro: nenhum arquivo .proto encontrado em $PROTO_DIR"
    exit 1
fi

mkdir -p "$OUT_DIR"

python3 -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR"/*.proto

sed -i 's/^import \(.*\)_pb2/from generated import \1_pb2/' "$OUT_DIR"/*_pb2_grpc.py

echo "Stubs gerados em $OUT_DIR/"
ls "$OUT_DIR"/*.py