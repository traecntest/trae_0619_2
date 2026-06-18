import time


class VirtualTimeEngine:
    @staticmethod
    def now_real():
        return time.time()

    @staticmethod
    def compute_current_virtual_seconds(session, now_real=None):
        if now_real is None:
            now_real = time.time()

        if session.status == "completed":
            return min(
                session.accumulated_virtual_seconds,
                session.total_planned_virtual_seconds,
            )

        if session.status == "paused":
            return session.accumulated_virtual_seconds

        effective_start = (
            session.last_pause_real_timestamp
            if session.last_pause_real_timestamp is not None
            else session.start_real_timestamp
        )
        delta_real = max(0.0, now_real - effective_start)
        delta_virtual = delta_real * session.speed_rate
        total = session.accumulated_virtual_seconds + delta_virtual
        return min(total, session.total_planned_virtual_seconds)

    @staticmethod
    def compute_progress(virtual_seconds, planned_seconds):
        if planned_seconds <= 0:
            return 0.0
        return min(1.0, max(0.0, virtual_seconds / planned_seconds))

    @staticmethod
    def build_state_payload(session, now_real=None):
        if now_real is None:
            now_real = time.time()
        virtual_seconds = VirtualTimeEngine.compute_current_virtual_seconds(session, now_real)
        progress = VirtualTimeEngine.compute_progress(
            virtual_seconds, session.total_planned_virtual_seconds
        )
        remaining = max(0.0, session.total_planned_virtual_seconds - virtual_seconds)
        return {
            "session_id": session.id,
            "title": session.title,
            "status": session.status,
            "speed_rate": session.speed_rate,
            "virtual_seconds": round(virtual_seconds, 3),
            "total_planned_virtual_seconds": session.total_planned_virtual_seconds,
            "accumulated_virtual_seconds": round(session.accumulated_virtual_seconds, 3),
            "progress": round(progress, 6),
            "remaining_virtual_seconds": round(remaining, 3),
            "real_now": now_real,
            "start_real_timestamp": session.start_real_timestamp,
        }
