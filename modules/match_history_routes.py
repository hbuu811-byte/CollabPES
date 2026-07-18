"""Route lịch sử trận đấu và endpoint tương thích gửi/xác nhận kết quả.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.route("/matches")
    @login_required
    def matches():
        user = current_user()
        history_view = (request.args.get("view") or "mine").strip()
        status_filter = (request.args.get("status") or "all").strip()
        query = (request.args.get("q") or "").strip().casefold()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 20

        rows = list_matches()
        if history_view != "all":
            history_view = "mine"
            rows = [
                match for match in rows
                if user.get("id") in {match.get("player1_id"), match.get("player2_id")}
            ]

        if status_filter != "all":
            rows = [match for match in rows if match.get("status") == status_filter]

        if query:
            rows = [
                match for match in rows
                if query in " ".join([
                    str(match.get("player1_name") or ""),
                    str(match.get("player2_name") or ""),
                    str(match.get("team1") or ""),
                    str(match.get("team2") or ""),
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

