from flask import Flask, request, send_file
from celery import Celery, Task
from celery.result import AsyncResult
from pdf2zh import translate_stream
import tqdm
import json
import io
from pdf2zh.doclayout import ModelInstance
from pdf2zh.config import ConfigManager

flask_app = Flask("pdf2zh")
flask_app.config.from_mapping(
    CELERY=dict(
        broker_url=ConfigManager.get("CELERY_BROKER", "redis://127.0.0.1:6379/0"),
        result_backend=ConfigManager.get("CELERY_RESULT", "redis://127.0.0.1:6379/0"),
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=False,
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
    return {"status": "ok", "service": "pdf2zh-api"}, 200


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
    file = request.files["file"]
    stream = file.stream.read()
    print(f"DEBUG [Backend]: Received file, size={len(stream)} bytes")
    print(f"DEBUG [Backend]: Form data: {request.form.get('data')}")
    args = json.loads(request.form.get("data"))
    print(f"DEBUG [Backend]: Translation args: {args}")
    task = translate_task.delay(stream, args)
    print(f"DEBUG [Backend]: Task created with id={task.id}")
    return {"id": task.id}


@flask_app.route("/v1/translate/<id>", methods=["GET"])
def get_translate_task(id: str):
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
        except Exception as e:
            print(f"WARNING [Backend]: Could not inspect workers: {e}")
    
    if state == "PROGRESS":
        return {"state": state, "info": result.info}
    else:
        return {"state": state}


@flask_app.route("/v1/translate/<id>", methods=["DELETE"])
def delete_translate_task(id: str):
    result: AsyncResult = celery_app.AsyncResult(id)
    result.revoke(terminate=True)
    return {"state": str(result.state)}


@flask_app.route("/v1/translate/<id>/<format>")
def get_translate_result(id: str, format: str):
    result = celery_app.AsyncResult(id)
    if not result.ready():
        return {"error": "task not finished"}, 400
    if not result.successful():
        return {"error": "task failed"}, 400
    doc_mono, doc_dual = result.get()
    to_send = doc_mono if format == "mono" else doc_dual
    return send_file(io.BytesIO(to_send), "application/pdf")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 11008))
    flask_app.run(host="0.0.0.0", port=port)
