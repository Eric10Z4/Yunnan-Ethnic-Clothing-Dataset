"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const state = require("./review_state.js");
const info = { record_count: 2, fingerprint: "a".repeat(64) };
const items = [
    { item_id: "1001", image_id: "1001", path: "images/train/1001.jpg", ethnicity: "Fixture", split: "train", caption: "Synthetic fixture only.", source_page_url: "https://example.org/1" },
    { item_id: "1002", image_id: "1002", path: "images/test/1002.jpg", ethnicity: "Fixture", split: "test", caption: "Synthetic fixture only.", source_page_url: "" }
];
assert.equal(state.checkedItems(items).length, 2);
assert.equal(state.checkedItems([{ ...items[0], path: "../private.jpg" }]).length, 0);
assert.notEqual(state.storageKey(info), state.storageKey({ fingerprint: "b".repeat(64) }));
const saved = state.filterSaved({ "1001": { status: "PASS" }, "9999": { status: "FAIL" } }, items);
assert.deepEqual(state.summary(items, saved), { total: 2, pass: 1, fail: 0, pending: 1 });
const special = { "1001": { status: "FAIL", reason: 'comma, "quote"\nline', code: "OTHER", detail: "=SYNTHETIC_FORMULA", reviewed_at: "2026-01-01T00:00:00Z" } };
const csv = state.exportCsv(items, special, info, "EXPORT_TIME");
assert.match(csv, /"comma, ""quote""\nline"/);
assert.match(csv, /"'=SYNTHETIC_FORMULA"/);
assert.match(csv, /ui_review_only/); assert.match(csv, /PENDING/);
assert.match(csv, /2026-01-01T00:00:00Z/);

// A small fake DOM exercises the real controller, not any production review.
const elements = new Map();
function element(id) {
    if (!elements.has(id)) elements.set(id, { id, style: {}, hidden: false, value: "", textContent: "", removeAttribute(name) { delete this[name]; }, focus() {} });
    return elements.get(id);
}
const buttons = Array.from({ length: 8 }, () => ({ disabled: false }));
const storage = new Map(); let clicked = false;
const listeners = {};
const context = {
    window: { ReviewState: state, AUDIT_ITEMS: items, AUDIT_DATASET: info, addEventListener(name, fn) { listeners[name] = fn; } },
    document: { getElementById: element, querySelectorAll: () => buttons, activeElement: { tagName: "BODY" }, body: { appendChild() {} }, createElement: () => ({ click() { clicked = true; }, remove() {} }) },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
    Blob, URL: { createObjectURL: () => "blob:synthetic-fixture", revokeObjectURL() {} }, Date, setTimeout: fn => fn()
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "review.js"), "utf8"), context);
listeners.load();
assert.equal(element("mainImage").src, "../dataset/images/train/1001.jpg");
assert.ok(buttons.every(button => button.disabled));
element("mainImage").onerror(); context.window.decidePass();
assert.equal(storage.size, 0, "Missing images must not create a verdict");
assert.match(element("imageStatus").textContent, /主集图片需另行提供/);
element("mainImage").onload(); context.window.decideFail("fixture,reason", "OTHER", "fixture detail");
assert.equal(element("mainImage").src, "../dataset/images/test/1002.jpg");
element("mainImage").onload(); context.window.decidePass();
assert.match(element("statTotal").textContent, /2 \/ 2/);
const persisted = JSON.parse(storage.get(state.storageKey(info)));
assert.equal(persisted["1001"].status, "FAIL"); assert.equal(persisted["1002"].status, "PASS");
assert.ok(persisted["1001"].reviewed_at);
context.window.exportResults(); assert.ok(clicked);

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
for (const asset of ["data.js", "review_state.js", "review.js"]) assert.ok(html.includes(`src="${asset}"`));
assert.ok(!html.includes("1603"));
console.log("Synthetic review-state/controller checks passed (no production review records written).");
