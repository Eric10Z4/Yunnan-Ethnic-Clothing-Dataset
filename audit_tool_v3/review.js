(function () {
    "use strict";
    const helpers = window.ReviewState;
    const supplied = window.AUDIT_ITEMS || [];
    const info = window.AUDIT_DATASET || {};
    const items = helpers.checkedItems(supplied);
    const storageKey = helpers.storageKey(info);
    let results = Object.create(null), currentIndex = 0, imageReady = false, indexReady = false;
    const el = id => document.getElementById(id);
    const current = () => items[currentIndex];
    function notice(text) { el("reviewNotice").textContent = text; }
    function controls(enabled) {
        document.querySelectorAll(".controls-container button").forEach(button => { button.disabled = !enabled; });
    }
    function stats() {
        const s = helpers.summary(items, results), done = s.pass + s.fail;
        el("statTotal").textContent = `总进度: ${done} / ${s.total} (${s.total ? (done / s.total * 100).toFixed(1) : "0.0"}%)`;
        el("statPass").textContent = `✅ 合格: ${s.pass}`;
        el("statFail").textContent = `❌ 不合格: ${s.fail}`;
        el("statPending").textContent = `⏳ 待审: ${s.pending}`;
    }
    function render() {
        if (!indexReady) return;
        const item = current();
        imageReady = false; controls(false);
        if (!item) return;
        const image = el("mainImage"), status = el("imageStatus");
        image.hidden = true; status.hidden = false;
        status.textContent = "正在加载本地图像…";
        const id = item.image_id;
        image.onload = function () {
            if (!current() || current().image_id !== id) return;
            imageReady = true; image.hidden = false; status.hidden = true; controls(true);
        };
        image.onerror = function () {
            if (!current() || current().image_id !== id) return;
            imageReady = false; image.hidden = true; status.hidden = false; controls(false);
            status.textContent = `未找到本地图像：dataset/${item.path}\n主集图片需另行提供，仓库不包含全量图片。补齐原目录后刷新即可；缺图时不允许作出判定。`;
        };
        image.src = helpers.imageUrl(item);
        el("infoIndex").textContent = `#${id}（第 ${currentIndex + 1} / ${items.length} 张）`;
        el("infoEthnicity").textContent = item.ethnicity;
        el("infoFilename").textContent = item.path;
        el("infoSplit").textContent = item.split;
        el("infoCaption").textContent = item.caption;
        const source = el("infoSource");
        if (/^https?:\/\//i.test(item.source_page_url || "")) {
            source.href = item.source_page_url; source.textContent = "打开公开来源页面"; source.hidden = false;
        } else { source.removeAttribute("href"); source.textContent = "未提供可公开链接"; source.hidden = false; }
        el("jumpBox").textContent = `${currentIndex + 1} / ${items.length}`;
        const row = results[id], stamp = el("stamp");
        el("rowFailReason").style.display = row && row.status === "FAIL" ? "block" : "none";
        if (row) {
            const passed = row.status === "PASS";
            stamp.className = "image-stamp " + (passed ? "stamp-pass" : "stamp-fail");
            stamp.textContent = passed ? "UI 判定 PASS" : "UI 判定 FAIL";
            el("infoMyDecision").textContent = passed ? "✅ 本次界面判定：合格" : "❌ 本次界面判定：不合格";
            el("infoFailReason").textContent = `${row.reason} (${row.detail || row.code})`;
        } else { stamp.className = "image-stamp"; el("infoMyDecision").textContent = "⏳ 本次界面待评审"; }
    }
    function persist() {
        try { localStorage.setItem(storageKey, JSON.stringify(results)); }
        catch (_) { notice("浏览器未允许持久保存。请及时导出本次评审CSV；本工具不改写数据集文件。"); }
    }
    function decide(status, reason, code, detail) {
        if (!indexReady || !current() || !imageReady) return;
        results[current().image_id] = { status, reason, code, detail: detail || "", reviewed_at: new Date().toISOString() };
        persist(); stats();
        if (currentIndex < items.length - 1) currentIndex++;
        render();
    }
    window.decidePass = () => decide("PASS", "合格", "NONE", "");
    window.decideFail = (reason, code, detail) => decide("FAIL", reason, code, detail);
    window.nextItem = function () { if (currentIndex < items.length - 1) { currentIndex++; render(); } };
    window.prevItem = function () { if (currentIndex > 0) { currentIndex--; render(); } };
    window.jumpToNextPending = function () {
        const next = items.findIndex((item, index) => index > currentIndex && !results[item.image_id]);
        const any = items.findIndex(item => !results[item.image_id]);
        if (next !== -1 || any !== -1) { currentIndex = next !== -1 ? next : any; render(); }
        else if (items.length) notice(`当前索引的 ${items.length} 张图片均已有UI评审记录，可导出CSV；标注真值未改动。`);
    };
    window.promptOtherReason = function () {
        if (!current() || !imageReady) return;
        el("inputOtherReason").value = ""; el("modalOther").style.display = "flex"; el("inputOtherReason").focus();
    };
    window.closeModal = id => { el(id).style.display = "none"; };
    window.confirmOtherReason = function () {
        const text = el("inputOtherReason").value.trim() || "其他原因";
        window.closeModal("modalOther"); decide("FAIL", "其他原因", "OTHER", text);
    };
    window.exportResults = function () {
        if (!indexReady || !items.length) return;
        const blob = new Blob([helpers.exportCsv(items, results, info, new Date().toISOString())], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob), link = document.createElement("a");
        link.href = url; link.download = `YECID_UI评审_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    window.addEventListener("keydown", function (event) {
        if (el("modalOther").style.display === "flex") {
            if (event.key === "Enter") window.confirmOtherReason();
            if (event.key === "Escape") window.closeModal("modalOther");
            return;
        }
        const activeTag = document.activeElement && document.activeElement.tagName;
        if (["INPUT", "TEXTAREA", "SELECT"].includes(activeTag) || event.ctrlKey || event.metaKey || event.altKey) return;
        if (["A", "BUTTON"].includes(activeTag) && (event.key === "Enter" || event.code === "Space")) return;
        const key = event.key.toUpperCase();
        if (key === "J" || event.code === "Space" || event.key === "Enter") { event.preventDefault(); window.decidePass(); }
        else if (event.key === "ArrowRight") window.nextItem();
        else if (event.key === "ArrowLeft") window.prevItem();
        else if (key === "7") window.promptOtherReason();
        else {
            const reasons = { "1": ["插画/手绘/3D/AI生成", "NOT_REAL_PHOTO"], "2": ["纯脸特写/缺乏服饰", "FACE_ONLY_NO_CLOTHING"], "3": ["方形布料/面料桌布", "NOT_GARMENT"], "4": ["现代便装/非少数民族", "INVALID_ETHNIC_COSTUME"], "5": ["多人合影/群演照片", "MULTI_PERSON"], "6": ["抠图破损/严重污斑", "BAD_SEGMENTATION"] };
            if (reasons[key]) window.decideFail(...reasons[key]);
        }
    });
    window.addEventListener("load", function () {
        controls(false); stats();
        if (!items.length || items.length !== supplied.length || info.record_count !== items.length || !/^[a-f0-9]{64}$/.test(info.fingerprint || "")) {
            el("imageStatus").textContent = "未加载到完整有效的评审索引。请按 audit_tool_v3/README.md 生成 data.js 后重新打开页面。";
            notice("索引缺失或不一致，未启用评审；数据集文件未改动。");
            return;
        }
        indexReady = true;
        try { results = helpers.filterSaved(JSON.parse(localStorage.getItem(storageKey) || "{}"), items); }
        catch (_) { results = Object.create(null); }
        const first = items.findIndex(item => !results[item.image_id]); currentIndex = first < 0 ? 0 : first;
        notice(`已加载当前快照 ${items.length} 条。UI记录按快照隔离，仅保存在此浏览器或导出CSV，不改写标注真值。`);
        render(); stats();
    });
})();
