"""Route lịch sử trận đấu.

Collap_V1.13.3m:
- bảo vệ chế độ xem toàn hệ thống bằng công tắc Admin;
- bộ lọc Đã hủy / Bỏ cuộc nhận mọi bản ghi phạt, kể cả thiếu đối thủ.
"""


def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    def _history_safe_delta(value):
        try:
            return int(round(float(value or 0)))
        except (TypeError, ValueError, OverflowError):
            return 0

    def _is_cancelled_or_forfeit_history(match):
        """Nhận diện trận hủy/bỏ cuộc mà không yêu cầu đủ hai người chơi."""
        if not isinstance(match, dict):
            return False
        if str(match.get("status") or "").strip() == "cancelled":
            return True

        checker = globals().get("is_forfeit_match")
        if callable(checker):
            try:
                if checker(match):
                    return True
            except Exception:
                pass

        note = str(match.get("note") or "").casefold()
        has_forfeit_note = any(token in note for token in (
            "[forfeit:", "bỏ cuộc", "bỏ trận", "bỏ dở", "rời phòng sau khi",
        ))
        has_negative_delta = (
            _history_safe_delta(match.get("delta1")) < 0
            or _history_safe_delta(match.get("delta2")) < 0
        )
        # Không gom trận confirmed thua bình thường vào bộ lọc bỏ cuộc.
        return has_forfeit_note or (
            has_negative_delta and str(match.get("status") or "") != "confirmed"
        )

    @app.route("/matches")
    @login_required
    def matches():
        user = current_user()
        requested_view = (request.args.get("view") or "mine").strip()
        status_filter = (request.args.get("status") or "all").strip()
        query = (request.args.get("q") or "").strip().casefold()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 20

        global_history_enabled = bool(
            system_feature_enabled("match_history_all_enabled")
        )
        can_view_all_history = bool(
            global_history_enabled or is_admin_user(user)
        )
        history_view = "all" if requested_view == "all" and can_view_all_history else "mine"

        rows = list_matches()
        if history_view != "all":
            user_id = user.get("id")
            rows = [
                match for match in rows
                if user_id in {match.get("player1_id"), match.get("player2_id")}
            ]

        if status_filter == "cancelled":
            rows = [match for match in rows if _is_cancelled_or_forfeit_history(match)]
        elif status_filter != "all":
            rows = [match for match in rows if match.get("status") == status_filter]

        if query:
            rows = [
                match for match in rows
                if query in " ".join([
                    str(match.get("player1_name") or ""),
                    str(match.get("player2_name") or ""),
                    str(match.get("team1") or ""),
                    str(match.get("team2") or ""),
                    str(match.get("note") or ""),
                ]).casefold()
            ]

        total_items = len(rows)
        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        history_viewer_id = user.get("id") if history_view == "mine" else None
        page_rows = [
            decorate_match_for_view(match, history_viewer_id)
            for match in rows[start:start + per_page]
        ]

        return render_template(
            "matches.html",
            matches=page_rows,
            history_view=history_view,
            can_view_all_history=can_view_all_history,
            global_history_enabled=global_history_enabled,
            status_filter=status_filter,
            q=request.args.get("q", ""),
            page=page,
            total_pages=total_pages,
            total_items=total_items,
        )

    @app.route("/submit-result")
    @login_required
    def submit_result():
        flash("Từ V1.2, kết quả được nhập trong Phòng đấu.", "warning")
        return redirect(url_for("rooms"))

    @app.route("/confirm-result")
    @login_required
    def confirm_result():
        flash("Từ V1.2, kết quả được xác nhận trong Phòng đấu.", "warning")
        return redirect(url_for("rooms"))
