from PySide6.QtCore import QRunnable, QObject, Signal

class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)


class Worker(QRunnable):
    """Worker thread for running functions in the background."""

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        """Execute the worker's function and emit signals."""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit((type(e), e, e.__traceback__))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()