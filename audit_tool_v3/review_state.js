/* Pure review-state helpers. UI records are separate from dataset annotations. */
(function (root, factory) {
    if (typeof module === "object" && module.exports) module.exports = factory();
    else root.ReviewState = factory();
})(typeof window !== "undefined" ? window : globalThis, function () {
    "use strict";
    function checkedItems(value) {
        if (!Array.isArray(value)) return [];
        const seen = new Set();
        return value.filter(function (item) {
            if (!item || !/^\d{4}$/.test(item.image_id) || item.item_id !== item.image_id || seen.has(item.image_id)) return false;
            if (!/^(train|val|test)$/.test(item.split) || item.path !== `images/${item.split}/${item.image_id}.jpg`) return false;
            if (typeof item.ethnicity !== "string" || typeof item.caption !== "string") return false;
            seen.add(item.image_id);
            return true;
        });
    }
    function storageKey(info) {
        const fingerprint = info && /^[a-f0-9]{64}$/.test(info.fingerprint) ? info.fingerprint : "empty";
        return "YECID_V3_UI_REVIEW_" + fingerprint;
    }
    function filterSaved(value, items) {
        const valid = Object.create(null);
        if (!value || typeof value !== "object") return valid;
        items.forEach(function (item) {
            const row = value[item.image_id];
            if (row && ["PASS", "FAIL"].includes(row.status)) {
                valid[item.image_id] = {
                    status: row.status,
                    reason: typeof row.reason === "string" ? row.reason : "",
                    code: typeof row.code === "string" ? row.code : "",
                    detail: typeof row.detail === "string" ? row.detail : "",
                    reviewed_at: typeof row.reviewed_at === "string" ? row.reviewed_at : ""
                };
            }
        });
        return valid;
    }
    function summary(items, results) {
        let pass = 0, fail = 0;
        items.forEach(function (item) {
            const row = results[item.image_id];
            if (row && row.status === "PASS") pass++;
            if (row && row.status === "FAIL") fail++;
        });
        return { total: items.length, pass, fail, pending: items.length - pass - fail };
    }
    function csvCell(value) {
        let text = value == null ? "" : String(value);
        // Quoting alone does not prevent spreadsheet formula execution.
        if (/^[\t\r\n]/.test(text) || /^\s*[=+\-@]/.test(text)) text = "'" + text;
        return '"' + text.replace(/"/g, '""') + '"';
    }
    function exportCsv(items, results, info, exportedAt) {
        const rows = [["image_id", "path", "ethnicity", "split", "record_kind", "ui_decision", "fail_reason", "fail_code", "fail_detail", "source_page_url", "dataset_fingerprint", "reviewed_at", "exported_at"]];
        items.forEach(function (item) {
            const row = results[item.image_id];
            rows.push([item.image_id, item.path, item.ethnicity, item.split, "ui_review_only", row ? row.status : "PENDING", row ? row.reason : "", row ? row.code : "", row ? row.detail : "", item.source_page_url || "", info.fingerprint || "", row ? row.reviewed_at : "", exportedAt]);
        });
        return "\uFEFF" + rows.map(row => row.map(csvCell).join(",")).join("\r\n");
    }
    function imageUrl(item) { return "../dataset/" + item.path; }
    return { checkedItems, storageKey, filterSaved, summary, csvCell, exportCsv, imageUrl };
});
