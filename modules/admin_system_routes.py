"""Route Admin hệ thống: maintenance, công tắc tính năng, backup/restore RP và chuyển chủ sở hữu.

Module đăng ký route theo dependency của app.py để giữ nguyên endpoint và tránh import vòng.
"""

from flask import abort

def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    @app.context_processor
    def inject_admin_feature_context():
        user = current_user()
        return {
            "app_name": APP_NAME, "app_version": APP_VERSION,
            "system_features": get_system_features(),
            "can_admin": lambda code: has_admin_permission(user, code),
            "admin_display_role": "Admin" if is_admin_user(user) else "",
            "is_test_mode": is_test_mode(),
            "simple_test_passwords_enabled": simple_test_passwords_enabled(),
            "minimum_password_length": minimum_password_length(),
            "maintenance_status": get_maintenance_status(),
        }

    @app.route("/admin/system/maintenance", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("system_features_manage")
    def admin_update_maintenance():
        close_at = _normalize_maintenance_input(request.form.get("close_at"))
        open_at = _normalize_maintenance_input(request.form.get("open_at"))
        close_dt = _parse_maintenance_time(close_at)
        open_dt = _parse_maintenance_time(open_at)
        if close_dt and open_dt and open_dt <= close_dt:
            flash("Thời gian mở máy chủ phải sau thời gian đóng máy chủ.", "danger")
            return redirect_admin("system")

        config = {
            "manual_closed": request.form.get("manual_closed") == "1",
            "close_at": close_at,
            "open_at": open_at,
            "message": (request.form.get("message") or "").strip()[:500]
                or _maintenance_default_config()["message"],
            "updated_at": now_iso(),
        }
        execute_query(
            db.table("system_settings").upsert({
                "setting_key": MAINTENANCE_SETTING_KEY,
                "setting_value": config,
                "updated_at": now_iso(),
            }, on_conflict="setting_key"),
            "update_server_maintenance_config",
            attempts=2,
        )
        _maintenance_cache["value"] = dict(config)
        _maintenance_cache["expires_at"] = time.time() + 15
        log_admin_action("Cập nhật trạng thái bảo trì máy chủ", "system", details=config)
        flash("Đã lưu trạng thái và lịch bảo trì máy chủ.", "success")
        return redirect_admin("system")


    @app.route("/admin/system/features", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("system_features_manage")
    def admin_update_system_features():
        previous_features = get_system_features()
        features = {key: request.form.get(key) == "1" for key in SYSTEM_FEATURE_DEFAULTS}
        execute_query(
            db.table("system_settings").upsert(
                {
                    "setting_key": "admin_system_features",
                    "setting_value": features,
                    "updated_at": now_iso(),
                },
                on_conflict="setting_key",
            ),
            "update_system_features",
        )

        # Khi Admin vừa tắt Giao hữu, đưa các phòng giao hữu đang mở về trạng thái
        # chờ sẵn sàng để người chơi không bị kẹt trong một tính năng đã khóa.
        if previous_features.get("friendly_enabled", True) and not features.get("friendly_enabled", False):
            execute_query(
                db.table("match_rooms").update({
                    "status": "waiting_ready",
                    "match_mode": "ranked",
                    "host_team": None,
                    "guest_team": None,
                    "host_team_overall": None,
                    "guest_team_overall": None,
                    "host_team_logo_url": None,
                    "guest_team_logo_url": None,
                    "host_team_league": None,
                    "guest_team_league": None,
                    "note": "Giao hữu đã được Admin tắt. Phòng đã trở về trạng thái chờ.",
                    "updated_at": now_iso(),
                }).eq("status", "friendly_playing"),
                "disable_active_friendly_rooms",
                attempts=2,
            )

        log_admin_action("Cập nhật công tắc hệ thống", "system", details=features)
        flash("Đã cập nhật các tính năng hệ thống.", "success")
        return redirect_admin("system")



    RP_USER_FIELDS = (
        "id", "rank_points", "wins", "draws", "losses", "total_matches",
        "goals_for", "goals_against", "streak", "loss_streak",
    )
    RP_MATCH_FIELDS = (
        "id", "delta1", "delta2", "rp_formula_version", "rp_details",
    )
    RP_BACKUP_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
    RP_BACKUP_MAX_ROWS = 100000


    def _select_all_rows(table_name, columns="*", page_size=1000):
        rows = []
        start = 0
        while True:
            result = execute_query(
                db.table(table_name).select(columns).range(start, start + page_size - 1),
                f"rp_backup_{table_name}_{start}", attempts=2,
            )
            batch = result.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                return rows
            start += page_size


    def _build_rp_backup_payload(actor):
        users = _select_all_rows("users", ",".join(RP_USER_FIELDS))
        matches = _select_all_rows("matches", ",".join(RP_MATCH_FIELDS))
        return {
            "metadata": {
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "backup_type": "rp_only",
                "format_version": 1,
                "created_at": now_iso(),
                "created_by_user_id": actor.get("id"),
                "created_by_username": actor.get("username"),
                "environment": APP_ENV,
            },
            "users": users,
            "matches": matches,
        }


    @app.route("/admin/rp/backup/download", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("rp_backup_restore")
    def admin_download_rp_backup():
        actor = current_user()
        if not is_test_mode() and request.form.get("confirm_text", "").strip() != "SAO LUU RP":
            flash("Trên Production, hãy nhập đúng: SAO LUU RP", "danger")
            return redirect_admin("rp-tools")
        try:
            payload = _build_rp_backup_payload(actor)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            json_name = f"PES_Arena_RP_Backup_{timestamp}.json"
            zip_name = f"PES_Arena_RP_Backup_{timestamp}.zip"
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(json_name, json.dumps(payload, ensure_ascii=False, indent=2, default=str))
                archive.writestr(
                    "README.txt",
                    "PES Arena RP-only backup. Restores RP/statistics/streaks and stored match deltas only.\n",
                )
            output.seek(0)
            log_admin_action("Sao lưu RP toàn hệ thống", "rp", details={
                "users": len(payload["users"]), "matches": len(payload["matches"]),
            })
            return send_file(output, mimetype="application/zip", as_attachment=True, download_name=zip_name)
        except Exception as exc:
            app.logger.exception("RP backup failed")
            flash(f"Không thể sao lưu RP: {exc}", "danger")
            return redirect_admin("rp-tools")


    def _read_rp_backup_upload(upload):
        if not upload or not upload.filename:
            raise ValueError("Hãy chọn file PES Arena RP Backup ZIP hoặc JSON.")
        raw = upload.read(RP_BACKUP_UPLOAD_MAX_BYTES + 1)
        if len(raw) > RP_BACKUP_UPLOAD_MAX_BYTES:
            raise ValueError("File RP Backup vượt quá giới hạn 10 MB.")
        filename = upload.filename.lower().strip()
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                candidates = [i for i in archive.infolist() if i.filename.lower().endswith(".json") and not i.is_dir()]
                if len(candidates) != 1:
                    raise ValueError("ZIP phải chứa đúng một file JSON RP Backup.")
                if candidates[0].file_size > RP_BACKUP_UPLOAD_MAX_BYTES * 5:
                    raise ValueError("JSON giải nén quá lớn.")
                raw = archive.read(candidates[0])
        elif not filename.endswith(".json"):
            raise ValueError("Chỉ chấp nhận file .zip hoặc .json.")
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except Exception as exc:
            raise ValueError("Không đọc được JSON trong file RP Backup.") from exc
        metadata = payload.get("metadata") or {}
        if metadata.get("app_name") != APP_NAME or metadata.get("backup_type") != "rp_only":
            raise ValueError("Đây không phải file PES Arena RP Backup hợp lệ.")
        users = payload.get("users")
        matches = payload.get("matches")
        if not isinstance(users, list) or not isinstance(matches, list):
            raise ValueError("File thiếu danh sách users hoặc matches.")
        if len(users) + len(matches) > RP_BACKUP_MAX_ROWS:
            raise ValueError("File RP Backup vượt quá 100.000 bản ghi.")
        return payload


    def _restore_rp_backup_payload(payload):
        user_count = 0
        match_count = 0
        missing_users = 0
        missing_matches = 0
        for row in payload.get("users", []):
            user_id = row.get("id")
            if not user_id:
                continue
            values = {key: row.get(key) for key in RP_USER_FIELDS if key != "id"}
            result = execute_query(
                db.table("users").update(values).eq("id", user_id),
                "restore_rp_user", attempts=2,
            )
            if result.data:
                user_count += 1
            else:
                missing_users += 1
        for row in payload.get("matches", []):
            match_id = row.get("id")
            if not match_id:
                continue
            values = {key: row.get(key) for key in RP_MATCH_FIELDS if key != "id"}
            result = execute_query(
                db.table("matches").update(values).eq("id", match_id),
                "restore_rp_match", attempts=2,
            )
            if result.data:
                match_count += 1
            else:
                missing_matches += 1
        ttl_cache_delete("players_raw", "rooms_raw", "achievement_map")
        cache_delete("all_users")
        return {
            "users": user_count, "matches": match_count,
            "missing_users": missing_users, "missing_matches": missing_matches,
        }


    @app.route("/admin/rp/backup/restore", methods=["POST"])
    @login_required
    @admin_required
    @admin_permission_required("rp_backup_restore")
    def admin_restore_rp_backup():
        actor = current_user()
        if not is_test_mode():
            if not is_owner_user(actor):
                flash("Chỉ tài khoản sở hữu được khôi phục RP trên Production.", "danger")
                return redirect_admin("rp-tools")
            if actor.get("password_hash") != hash_password(request.form.get("current_password", "")):
                flash("Mật khẩu hiện tại không đúng.", "danger")
                return redirect_admin("rp-tools")
            if request.form.get("confirm_text", "").strip() != "KHOI PHUC RP":
                flash("Hãy nhập đúng: KHOI PHUC RP", "danger")
                return redirect_admin("rp-tools")
        try:
            payload = _read_rp_backup_upload(request.files.get("backup_file"))
            report = _restore_rp_backup_payload(payload)
            log_admin_action("Khôi phục RP toàn hệ thống", "rp", details={
                "source": payload.get("metadata", {}), "report": report,
            })
            flash(
                f"Đã khôi phục RP cho {report['users']} tài khoản và delta của {report['matches']} trận. "
                f"Không tìm thấy: {report['missing_users']} tài khoản, {report['missing_matches']} trận.",
                "success",
            )
        except Exception as exc:
            app.logger.exception("RP restore failed")
            log_admin_action("Khôi phục RP thất bại", "rp", details={"error": str(exc)[:500]})
            flash(f"Không thể khôi phục RP: {exc}", "danger")
        return redirect_admin("rp-tools")


    # Các route Backup toàn bộ dữ liệu từ V1.13.4 đã ngừng sử dụng.
    @app.route("/admin/backup/download", methods=["POST"])
    @app.route("/admin/backup/preview", methods=["POST"])
    @app.route("/admin/backup/restore", methods=["POST"])
    @login_required
    @admin_required
    def retired_full_database_backup_routes():
        abort(404)


    @app.route("/admin/ownership/transfer", methods=["POST"])
    @login_required
    @owner_required
    def admin_transfer_ownership():
        abort(404)
        actor = current_user()
        target_id = (request.form.get("target_user_id") or "").strip()
        current_password = request.form.get("current_password", "").strip()
        confirm_text = request.form.get("confirm_text", "").strip()
        if actor.get("password_hash") != hash_password(current_password):
            flash("Mật khẩu hiện tại của tài khoản sở hữu không đúng.", "danger")
            return redirect_admin("overview")
        if confirm_text != "CHUYEN GIAO":
            flash("Hãy nhập đúng CHUYEN GIAO để xác nhận.", "danger")
            return redirect_admin("overview")
        target = get_user(target_id)
        if not target or target.get("account_status") != "approved" or target.get("id") == actor.get("id"):
            flash("Tài khoản nhận chuyển giao không hợp lệ.", "danger")
            return redirect_admin("overview")

        full_permissions = {code: True for codes in ADMIN_PERMISSION_GROUPS.values() for code in codes}
        try:
            execute_query(db.table("users").update({
                "admin_level": "owner", "admin_permissions": full_permissions,
                "updated_at": now_iso(),
            }).eq("id", target["id"]), "transfer_owner_to_target")
            execute_query(db.table("users").update({
                "admin_level": "admin", "admin_permissions": full_permissions,
                "updated_at": now_iso(),
            }).eq("id", actor["id"]), "transfer_owner_from_actor")
        except Exception:
            app.logger.exception("Ownership transfer failed")
            # Best-effort restore the actor as owner if the second write failed.
            execute_query(db.table("users").update({"admin_level": "owner"}).eq("id", actor["id"]), "restore_owner_after_transfer_failure", attempts=2)
            raise
        log_admin_action("Chuyển giao quyền sở hữu", "user", target["id"], target.get("username"), f"Từ {actor.get('username')} sang {target.get('username')}")
        session.clear()
        flash("Đã chuyển giao quyền sở hữu. Hãy đăng nhập lại.", "success")
        return redirect(url_for("login"))

