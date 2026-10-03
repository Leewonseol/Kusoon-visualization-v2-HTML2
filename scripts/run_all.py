"""구순 temporal network 전체 실행: 데이터 → 시각화 → README.

실행 중 모든 소켓 연결을 차단·기록한다(socket guard). 검증 9번은 이 기록이 0건인지 확인한다.
"""
import socket
import sys
from pathlib import Path

NET_ATTEMPTS: list = []
_orig_connect = socket.socket.connect


def _guard(self, address):  # noqa: ANN001
    NET_ATTEMPTS.append(repr(address))
    raise ConnectionError(f"network access disabled in this pipeline: {address!r}")


socket.socket.connect = _guard
socket.create_connection = lambda *a, **k: _guard(None, a[0] if a else k)

sys.path.insert(0, str(Path(__file__).parent))
import gusun_pipeline as gp  # noqa: E402

if __name__ == "__main__":
    res = gp.run(NET_ATTEMPTS)
    if "--data-only" not in sys.argv:
        import gusun_viz as gv
        gv.build_all(res)
        import gusun_readme as gr
        gr.write_readme(res, NET_ATTEMPTS)
    print(res["val"].to_string(index=False))
    if (res["val"].result != "PASS").any():
        sys.exit(1)
