import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8080

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "index.html")
CSS_PATH = os.path.join(BASE_DIR, "static", "engine.css")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts_library")

os.makedirs(SCRIPTS_DIR, exist_ok=True)

MANDATORY_APPLIED_SCRIPTS = {}


def is_authorized(headers) -> bool:
    # وضع المطور: السماح المباشر بدون شاشة تسجيل دخول
    return True


def validate_script_syntax(language: str, code: str) -> tuple[bool, str]:
    forbidden_patterns = ["Runtime.getRuntime()", "ProcessBuilder", "system(", "popen("]
    for pattern in forbidden_patterns:
        if pattern in code:
            return False, f"تم حظر تعليمة خطرة بواسطة نظام الحماية: {pattern}"

    if not code.strip():
        return False, "لا يمكن تطبيق كود فارغ."

    if language == "java":
        if "class " not in code and "void " not in code:
            return False, "كود Java يجب أن يحتوي على class أو دالة void."
    elif language == "cpp":
        if "void " not in code and "struct " not in code:
            return False, "كود C++ يجب أن يحتوي على دالة void أو struct."
    else:
        return False, "اللغة غير مدعومة. اختر java أو cpp فقط."

    return True, "الكود سليم وجاهز للتطبيق الإجباري."


class EngineRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: str, content_type: str):
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(TEMPLATE_PATH, "text/html; charset=utf-8")
        elif parsed.path == "/static/engine.css":
            self._send_file(CSS_PATH, "text/css; charset=utf-8")
        elif parsed.path == "/api/mandatory-bindings":
            self._send_json(200, {"ok": True, "bindings": MANDATORY_APPLIED_SCRIPTS})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "صيغة JSON غير صالحة."})
            return

        if parsed.path == "/api/apply-script-mandatory":
            target_id = str(data.get("target_object_id", "")).strip()
            target_name = str(data.get("target_object_name", "")).strip()
            language = str(data.get("language", "")).strip().lower()
            code = str(data.get("code", ""))

            if not target_id:
                self._send_json(400, {"ok": False, "error": "يجب تحديد شخصية أو كائن أولاً لتطبيق الكود إجبارياً."})
                return

            valid, msg = validate_script_syntax(language, code)
            if not valid:
                self._send_json(400, {"ok": False, "error": msg})
                return

            ext = "java" if language == "java" else "cpp"
            script_filename = f"{target_id}_{language}.{ext}"
            script_path = os.path.join(SCRIPTS_DIR, script_filename)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            binding_record = {
                "target_object_id": target_id,
                "target_object_name": target_name,
                "language": language,
                "mandatory_applied": True,
                "script_file": script_filename,
                "code": code,
            }
            MANDATORY_APPLIED_SCRIPTS[target_id] = binding_record

            self._send_json(
                200,
                {
                    "ok": True,
                    "binding": binding_record,
                    "message": f"تم اعتماد وتطبيق كود ({language.upper()}) إجبارياً على الكائن: {target_name}",
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "Endpoint غير موجود."})


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), EngineRequestHandler)
    print(f"Nexus 3D Engine Server (Developer Direct Mode) running at http://{HOST}:{PORT}")
    server.serve_forever()