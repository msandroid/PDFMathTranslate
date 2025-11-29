from flask import Flask, request, send_file
from celery import Celery, Task
from celery.result import AsyncResult
from pdf2zh import translate_stream
import tqdm
import json
import io
import os
from pdf2zh.doclayout import ModelInstance
from pdf2zh.config import ConfigManager

flask_app = Flask("pdf2zh")

# Celeryワーカーの並行度を環境変数から取得（デフォルトは2、Railway推奨）
# Railwayなどのクラウド環境では、メモリ制限があるため低めの値が推奨されます
worker_concurrency = int(os.environ.get("CELERY_WORKER_CONCURRENCY", "2"))

# Redis接続URLの構築
# RailwayではREDISHOST環境変数が自動的に設定される場合がある
def get_redis_url():
    # REDISHOST環境変数が存在する場合、それを優先して使用（Railwayの自動設定）
    redis_host = os.environ.get("REDISHOST")
    if redis_host:
        redis_port = os.environ.get("REDISPORT", "6379")
        redis_password = os.environ.get("REDISPASSWORD", "")
        redis_db = os.environ.get("REDISDB", "0")
        
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    # CELERY_BROKER環境変数が明示的に設定されている場合、それを使用
    broker = ConfigManager.get("CELERY_BROKER")
    if broker and broker != "redis://127.0.0.1:6379/0":
        return broker
    
    # デフォルト値
    return "redis://127.0.0.1:6379/0"

redis_url = get_redis_url()

flask_app.config.from_mapping(
    CELERY=dict(
        broker_url=ConfigManager.get("CELERY_BROKER", redis_url),
        result_backend=ConfigManager.get("CELERY_RESULT", redis_url),
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=False,
        worker_concurrency=worker_concurrency,
    )
)


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.Task = FlaskTask
    celery_app.set_default()
    celery_app.autodiscover_tasks()
    app.extensions["celery"] = celery_app
    return celery_app


celery_app = celery_init_app(flask_app)


@flask_app.route("/", methods=["GET"])
@flask_app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        # Celeryワーカーの状態を確認
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        worker_status = "available" if active_workers else "unavailable"
        
        return {
            "status": "ok",
            "service": "pdf2zh-api",
            "workers": worker_status
        }, 200
    except Exception as e:
        # ワーカーの確認に失敗しても、APIサーバー自体は動作している
        return {
            "status": "ok",
            "service": "pdf2zh-api",
            "workers": "unknown",
            "warning": f"Could not check worker status: {str(e)}"
        }, 200


@celery_app.task(bind=True)
def translate_task(
    self: Task,
    stream: bytes,
    args: dict,
):
    print(f"DEBUG [Celery Worker]: translate_task started, task_id={self.request.id}")
    print(f"DEBUG [Celery Worker]: stream size={len(stream)} bytes, args={args}")
    
    def progress_bar(t: tqdm.tqdm):
        self.update_state(state="PROGRESS", meta={"n": t.n, "total": t.total})  # noqa
        print(f"DEBUG [Celery Worker]: Translating {t.n} / {t.total} pages")

    try:
        doc_mono, doc_dual = translate_stream(
            stream,
            callback=progress_bar,
            model=ModelInstance.value,
            **args,
        )
        print(f"DEBUG [Celery Worker]: Translation completed successfully, task_id={self.request.id}")
        return doc_mono, doc_dual
    except Exception as e:
        print(f"ERROR [Celery Worker]: Translation failed, task_id={self.request.id}, error={str(e)}")
        raise


@flask_app.route("/v1/translate", methods=["POST"])
def create_translate_tasks():
    try:
        # ファイルの存在確認
        if "file" not in request.files:
            print(f"ERROR [Backend]: No file in request")
            return {"status": "error", "code": 400, "message": "No file provided"}, 400
        
        file = request.files["file"]
        if file.filename == "":
            print(f"ERROR [Backend]: Empty filename")
            return {"status": "error", "code": 400, "message": "Empty filename"}, 400
        
        stream = file.stream.read()
        if len(stream) == 0:
            print(f"ERROR [Backend]: Empty file")
            return {"status": "error", "code": 400, "message": "Empty file"}, 400
        
        print(f"DEBUG [Backend]: Received file, size={len(stream)} bytes")
        
        # データの存在確認
        if "data" not in request.form:
            print(f"ERROR [Backend]: No data in form")
            return {"status": "error", "code": 400, "message": "No data provided"}, 400
        
        data_str = request.form.get("data")
        print(f"DEBUG [Backend]: Form data: {data_str}")
        
        try:
            args = json.loads(data_str)
        except json.JSONDecodeError as e:
            print(f"ERROR [Backend]: Invalid JSON in data: {e}")
            return {"status": "error", "code": 400, "message": f"Invalid JSON: {str(e)}"}, 400
        
        print(f"DEBUG [Backend]: Translation args: {args}")
        
        # Celeryワーカーの確認
        try:
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            if active_workers is None:
                print(f"WARNING [Backend]: No active Celery workers detected")
                return {
                    "status": "error",
                    "code": 503,
                    "message": "No Celery workers available. Please ensure the worker service is running."
                }, 503
        except Exception as e:
            print(f"WARNING [Backend]: Could not check Celery workers: {e}")
            # ワーカーの確認に失敗しても続行（接続の問題かもしれない）
        
        # タスクの作成
        try:
            task = translate_task.delay(stream, args)
            print(f"DEBUG [Backend]: Task created with id={task.id}")
            return {"id": task.id}
        except Exception as e:
            print(f"ERROR [Backend]: Failed to create task: {e}")
            return {
                "status": "error",
                "code": 500,
                "message": f"Failed to create translation task: {str(e)}"
            }, 500
            
    except Exception as e:
        print(f"ERROR [Backend]: Unexpected error in create_translate_tasks: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }, 500


@flask_app.route("/v1/translate/<id>", methods=["GET"])
def get_translate_task(id: str):
    try:
        result: AsyncResult = celery_app.AsyncResult(id)
        state = str(result.state)
        print(f"DEBUG [Backend]: Task status check - id={id}, state={state}")
        
        # Check if worker is actually running by inspecting the broker
        if state == "PENDING":
            try:
                # Check if task is in the queue
                inspect = celery_app.control.inspect()
                active_tasks = inspect.active()
                scheduled_tasks = inspect.scheduled()
                reserved_tasks = inspect.reserved()
                
                if active_tasks or scheduled_tasks or reserved_tasks:
                    print(f"DEBUG [Backend]: Workers are active. Active: {active_tasks}, Scheduled: {scheduled_tasks}, Reserved: {reserved_tasks}")
                else:
                    print(f"WARNING [Backend]: No active workers detected! Task {id} may never be processed.")
                    return {
                        "status": "error",
                        "code": 503,
                        "message": "No Celery workers available. Task is pending but no workers are running.",
                        "state": state
                    }, 503
            except Exception as e:
                print(f"WARNING [Backend]: Could not inspect workers: {e}")
        
        if state == "PROGRESS":
            return {"state": state, "info": result.info}
        elif state == "FAILURE":
            error_info = result.info
            error_message = str(error_info) if error_info else "Unknown error"
            print(f"ERROR [Backend]: Task {id} failed: {error_message}")
            return {
                "state": state,
                "error": error_message
            }
        else:
            return {"state": state}
    except Exception as e:
        print(f"ERROR [Backend]: Error checking task status: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }, 500


@flask_app.route("/v1/translate/<id>", methods=["DELETE"])
def delete_translate_task(id: str):
    result: AsyncResult = celery_app.AsyncResult(id)
    result.revoke(terminate=True)
    return {"state": str(result.state)}


@flask_app.route("/v1/translate/<id>/<format>")
def get_translate_result(id: str, format: str):
    try:
        if format not in ["mono", "dual"]:
            return {"status": "error", "code": 400, "message": "Invalid format. Must be 'mono' or 'dual'"}, 400
        
        result = celery_app.AsyncResult(id)
        if not result.ready():
            return {
                "status": "error",
                "code": 400,
                "message": "Task not finished yet",
                "state": str(result.state)
            }, 400
        
        if not result.successful():
            error_info = result.info
            error_message = str(error_info) if error_info else "Unknown error"
            print(f"ERROR [Backend]: Task {id} failed: {error_message}")
            return {
                "status": "error",
                "code": 500,
                "message": f"Task failed: {error_message}"
            }, 500
        
        doc_mono, doc_dual = result.get()
        to_send = doc_mono if format == "mono" else doc_dual
        return send_file(io.BytesIO(to_send), "application/pdf")
    except Exception as e:
        print(f"ERROR [Backend]: Error getting translation result: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }, 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 11008))
    flask_app.run(host="0.0.0.0", port=port)
