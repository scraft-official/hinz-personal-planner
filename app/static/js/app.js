document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  init();
  document.body.addEventListener("htmx:afterSwap", (evt) => {
    if (evt.target && evt.target.id === "schedule") {
      setupEntries();
    }
    if (evt.target && evt.target.id === "palette") {
      setupPalette();
    }
    setupIconPicker();
    setupQuickTaskModal();
    setupEntryNoteModal();
    setupAddBlockModal();
  });
});

function init() {
  setupPalette();
  setupEntries();
  setupSearch();
  setupDeleteButtons();
  setupIconPicker();
  setupQuickTaskModal();
  setupEntryNoteModal();
  setupAddBlockModal();
  setupThemeToggle();
}

/* ---------- THEME ---------- */
function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else if (saved === "light") {
    document.documentElement.removeAttribute("data-theme");
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
}

function setupThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  if (!btn || btn.dataset.bound === "true") return;
  btn.addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("theme", "light");
    } else {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("theme", "dark");
    }
  });
  btn.dataset.bound = "true";
}

/* ---------- PALETTE ---------- */
function setupPalette() {
  const palette = document.getElementById("palette");
  if (!palette) return;

  palette.addEventListener("click", (e) => {
    // Handle delete button click
    const deleteBtn = e.target.closest(".palette-delete-btn");
    if (deleteBtn) {
      e.preventDefault();
      e.stopPropagation();
      const blockId = deleteBtn.dataset.blockId;
      if (blockId && confirm("Delete this block type? All entries using it will also be deleted.")) {
        fetch(`/blocks/${blockId}`, {
          method: "DELETE",
          headers: { "HX-Request": "true" },
        })
          .then((r) => r.text())
          .then((html) => {
            const current = document.getElementById("palette");
            if (current) {
              const wrapper = document.createElement("div");
              wrapper.innerHTML = html;
              const next = wrapper.querySelector("#palette") || wrapper.firstElementChild;
              if (next) {
                current.replaceWith(next);
                setupPalette();
              }
            }
          })
          .catch(console.error);
      }
      return;
    }

    const card = e.target.closest(".palette-card");
    if (!card) return;
    selectPaletteCard(card, palette);
  });

  palette.querySelectorAll(".palette-card").forEach((card) => {
    card.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      if (e.target.closest(".palette-delete-btn")) return;
      e.preventDefault();
      startPaletteDrag(e, card);
    });
  });
}

function selectPaletteCard(card, palette) {
  palette.querySelectorAll(".palette-card").forEach((c) => c.classList.remove("active"));
  card.classList.add("active");
}

function getSelectedDuration() {
  const select = document.getElementById("duration-select");
  return select ? parseInt(select.value, 10) : 60;
}

function getWeekStart() {
  const schedule = document.getElementById("schedule");
  return schedule ? schedule.dataset.weekStart : null;
}

function startPaletteDrag(event, card) {
  const schedule = document.getElementById("schedule");
  if (!schedule) return;
  const meta = extractMeta(schedule);
  if (!meta) return;

  window.dragState = {
    mode: "create",
    blockId: card.dataset.blockId,
    duration: getSelectedDuration(),
    color: card.dataset.color || "#0ea5e9",
    meta,
    indicator: createIndicator(),
    target: null,
  };

  document.body.style.cursor = "grabbing";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

/* ---------- SEARCH ---------- */
function setupSearch() {
  const searchInput = document.getElementById("block-search");
  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();
    const cards = document.querySelectorAll(".palette-card");
    cards.forEach((card) => {
      const name = (card.dataset.name || "").toLowerCase();
      card.style.display = name.includes(query) || query === "" ? "" : "none";
    });
  });
}

/* ---------- DELETE BUTTONS ---------- */
function setupDeleteButtons() {
  // Use event delegation on body for delete buttons
  document.body.addEventListener("click", (e) => {
    const btn = e.target.closest(".entry-delete-btn");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const entryId = btn.dataset.entryId;
    if (!entryId) return;

    // Prevent double-click issues
    if (btn.disabled) return;
    btn.disabled = true;

    const weekStart = getWeekStart();
    let url = `/entries/${entryId}`;
    if (weekStart) url += `?week_start=${weekStart}`;

    fetch(url, {
      method: "DELETE",
      headers: { "HX-Request": "true" },
    })
      .then((r) => r.text())
      .then(replaceScheduleHtml)
      .catch(console.error);
  });
}

/* ---------- ENTRIES ---------- */
function setupEntries() {
  const schedule = document.getElementById("schedule");
  if (!schedule) return;
  const meta = extractMeta(schedule);
  if (!meta) return;

  schedule.querySelectorAll(".entry").forEach((entry) => {
    entry.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      if (e.target.closest(".entry-delete-btn")) return;
      if (e.target.closest(".entry-resize-handle")) {
        e.preventDefault();
        e.stopPropagation();
        startResize(e, entry, meta);
        return;
      }
      if (e.target.closest(".entry-title-text")) {
        // Let title clicks pass through to open notes without starting drag
        return;
      }
      e.preventDefault();
      startEntryDrag(e, entry, meta);
    });

    entry.addEventListener("click", (e) => handleEntryClick(e, entry));
  });
}

function startEntryDrag(event, entry, meta) {
  window.dragState = {
    mode: "move",
    entry,
    id: entry.dataset.entryId,
    duration: parseInt(entry.dataset.duration, 10),
    startMinute: parseInt(entry.dataset.startMinute, 10),
    day: entry.dataset.day,
    color: entry.dataset.color || "#0ea5e9",
    meta,
    indicator: createIndicator(),
    target: null,
  };

  entry.classList.add("dragging");
  document.body.style.cursor = "grabbing";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

function startResize(event, entry, meta) {
  window.dragState = {
    mode: "resize",
    entry,
    id: entry.dataset.entryId,
    startMinute: parseInt(entry.dataset.startMinute, 10),
    duration: parseInt(entry.dataset.duration, 10),
    day: entry.dataset.day,
    color: entry.dataset.color || "#0ea5e9",
    meta,
    indicator: createIndicator(),
    target: null,
  };

  entry.classList.add("dragging");
  document.body.style.cursor = "ns-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
}

/* ---------- COLLISION DETECTION ---------- */
function getEntriesInCol(col, excludeEntryId) {
  const entries = col.querySelectorAll(".entry");
  const result = [];
  entries.forEach((entry) => {
    const id = entry.dataset.entryId;
    if (excludeEntryId && id === String(excludeEntryId)) return;
    result.push({
      id,
      start: parseInt(entry.dataset.startMinute, 10),
      end: parseInt(entry.dataset.endMinute, 10),
    });
  });
  return result;
}

function hasCollision(entries, startMinute, endMinute) {
  for (const e of entries) {
    // Check if ranges overlap
    if (startMinute < e.end && endMinute > e.start) {
      return true;
    }
  }
  return false;
}

/* ---------- DRAG LOGIC ---------- */
function onDragMove(event) {
  const ds = window.dragState;
  if (!ds) return;

  const col = findDayCol(event.clientX, event.clientY);
  if (!col) {
    ds.indicator.style.display = "none";
    ds.target = null;
    return;
  }
  ds.indicator.style.display = "";

  const { meta, mode } = ds;
  const rect = col.getBoundingClientRect();
  const y = Math.max(0, event.clientY - rect.top);
  
  // Snap to slot grid
  const slots = Math.floor(y / meta.slotHeight);
  let startMinute = meta.dayStart + slots * meta.slotMinutes;
  let duration = ds.duration;

  if (mode === "resize") {
    // Keep original start, adjust duration based on cursor
    startMinute = ds.startMinute;
    const entryTop = ((ds.startMinute - meta.dayStart) / meta.slotMinutes) * meta.slotHeight;
    const newHeight = Math.max(0, y - entryTop);
    const durationSlots = Math.max(2, Math.round(newHeight / meta.slotHeight)); // Min 30 min (2 slots)
    duration = durationSlots * meta.slotMinutes;
  }

  // Enforce minimum 30 minutes
  duration = Math.max(30, duration);

  // Clamp
  startMinute = Math.max(meta.dayStart, Math.min(startMinute, meta.dayEnd - duration));
  if (startMinute + duration > meta.dayEnd) {
    duration = meta.dayEnd - startMinute;
  }

  const endMinute = startMinute + duration;

  // Check for collision
  const excludeId = mode === "move" || mode === "resize" ? ds.id : null;
  const existingEntries = getEntriesInCol(col, excludeId);
  const collision = hasCollision(existingEntries, startMinute, endMinute);

  if (collision) {
    ds.indicator.classList.add("invalid");
    ds.target = null; // Prevent drop
  } else {
    ds.indicator.classList.remove("invalid");
    ds.target = {
      day: col.dataset.day,
      startMinute,
      duration,
    };
  }

  placeIndicator(ds.indicator, col, startMinute, duration, meta, collision ? "#ef4444" : ds.color);
}

function onDragEnd() {
  const ds = window.dragState;
  if (!ds) return;

  // Cleanup
  if (ds.entry) ds.entry.classList.remove("dragging");
  if (ds.indicator) ds.indicator.remove();
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", onDragEnd);

  // Always suppress click after any drag operation
  suppressEntryClick();

  if (!ds.target) {
    window.dragState = null;
    return;
  }

  const { target, mode } = ds;
  const weekStart = getWeekStart();

  if (mode === "move" || mode === "resize") {
    const fd = new FormData();
    fd.append("day", target.day);
    fd.append("start_minute", String(target.startMinute));
    fd.append("duration_minutes", String(target.duration));
    if (weekStart) fd.append("week", weekStart);
    fetch(`/entries/${ds.id}/move`, {
      method: "POST",
      headers: { "HX-Request": "true" },
      body: fd,
    })
      .then((r) => r.text())
      .then(replaceScheduleHtml)
      .catch(console.error)
      .finally(() => {
        window.dragState = null;
      });
  } else if (mode === "create") {
    const fd = new FormData();
    fd.append("day", target.day);
    fd.append("start_time", minutesToTime(target.startMinute));
    fd.append("duration_minutes", String(ds.duration));
    fd.append("block_type_id", ds.blockId);
    fd.append("note", "");
    fd.append("week", weekStart || "");
    fetch("/entries", {
      method: "POST",
      headers: { "HX-Request": "true" },
      body: fd,
    })
      .then((r) => r.text())
      .then(replaceScheduleHtml)
      .catch(console.error)
      .finally(() => {
        window.dragState = null;
      });
  }
}

/* ---------- HELPERS ---------- */
function extractMeta(schedule) {
  if (!schedule.dataset.dayStart) return null;
  return {
    dayStart: parseInt(schedule.dataset.dayStart, 10),
    dayEnd: parseInt(schedule.dataset.dayEnd, 10),
    slotMinutes: parseInt(schedule.dataset.slotMinutes, 10),
    slotHeight: parseInt(schedule.dataset.slotHeight, 10),
    dayOrder: schedule.dataset.dayOrder.split(","),
  };
}

function createIndicator() {
  const el = document.createElement("div");
  el.className = "drop-indicator";
  return el;
}

function placeIndicator(indicator, col, startMinute, duration, meta, color) {
  const topPx = ((startMinute - meta.dayStart) / meta.slotMinutes) * meta.slotHeight;
  const heightPx = (duration / meta.slotMinutes) * meta.slotHeight;
  indicator.style.top = `${topPx}px`;
  indicator.style.height = `${heightPx}px`;
  indicator.style.borderColor = color || "#0ea5e9";
  indicator.style.backgroundColor = (color || "#0ea5e9") + "22";
  if (indicator.parentElement !== col) {
    col.appendChild(indicator);
  }
}

function findDayCol(clientX, clientY) {
  const els = document.elementsFromPoint(clientX, clientY);
  for (const el of els) {
    const col = el.closest(".day-col");
    if (col) return col;
  }
  return null;
}

function replaceScheduleHtml(html) {
  const current = document.getElementById("schedule");
  if (!current) return;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = html;
  const next = wrapper.querySelector("#schedule") || wrapper.firstElementChild;
  if (next) {
    current.replaceWith(next);
    setupEntries();
  }
}

function minutesToTime(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/* ---------- ICON PICKER ---------- */
function setupIconPicker() {
  const pickers = document.querySelectorAll(".icon-picker");
  pickers.forEach((picker) => {
    if (picker.dataset.bound === "true") return;
    const hidden = picker.querySelector('input[name="icon"]');
    if (!hidden) return;
    picker.addEventListener("click", (e) => {
      const option = e.target.closest(".icon-option");
      if (!option || !picker.contains(option)) return;
      e.preventDefault();
      hidden.value = option.dataset.icon;
      picker.querySelectorAll(".icon-option").forEach((btn) => btn.classList.remove("is-selected"));
      option.classList.add("is-selected");
    });
    picker.dataset.bound = "true";
  });
}

/* ---------- QUICK TASK MODAL ---------- */
function setupQuickTaskModal() {
  const modal = document.getElementById("quick-task-modal");
  const trigger = document.getElementById("quick-task-btn");
  if (!modal || !trigger || modal.dataset.bound === "true") return;
  const form = document.getElementById("quick-task-form");
  const closeTargets = modal.querySelectorAll("[data-close-modal]");

  const openModal = () => {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    const firstInput = form ? form.querySelector("input[name='title']") : null;
    window.setTimeout(() => firstInput && firstInput.focus(), 10);
  };

  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  const handleSuccess = () => {
    if (form) form.reset();
    const daySelect = form ? form.querySelector("select[name='day']") : null;
    if (daySelect) {
      const todayOption = Array.from(daySelect.options).find((opt) => opt.defaultSelected);
      if (todayOption) daySelect.value = todayOption.value;
    }
    closeModal();
  };

  trigger.addEventListener("click", openModal);
  closeTargets.forEach((el) => el.addEventListener("click", closeModal));
  modal.addEventListener("click", (e) => {
    if (e.target.matches("[data-close-modal]")) {
      closeModal();
    }
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  // Listen for successful HTMX request from the quick task form
  if (form) {
    form.addEventListener("htmx:afterRequest", (evt) => {
      if (evt.detail.successful) {
        handleSuccess();
      } else if (evt.detail.xhr && evt.detail.xhr.status === 409) {
        // Collision detected - time slot occupied
        alert("This time slot is already occupied. Please choose a different time.");
      }
    });
  }

  window.closeQuickTaskModal = closeModal;
  window.handleQuickTaskSuccess = handleSuccess;

  modal.dataset.bound = "true";
}

/* ---------- ENTRY NOTES ---------- */
function handleEntryClick(event, entry) {
  if (event.defaultPrevented) return;
  if (event.target.closest(".entry-delete-btn") || event.target.closest(".entry-resize-handle")) return;
  // Only open note modal when clicking on the title text
  const titleText = event.target.closest(".entry-title-text");
  if (!titleText) return;
  const entryId = titleText.dataset.entryId || entry.dataset.entryId;
  if (!entryId) return;
  if (isEntryClickSuppressed()) return;
  event.preventDefault();
  event.stopPropagation();
  if (typeof openEntryNoteModal === "function") {
    openEntryNoteModal(entryId);
  }
}

function suppressEntryClick() {
  window.entryClickSuppress = {
    until: Date.now() + 300,
  };
}

function isEntryClickSuppressed() {
  const sup = window.entryClickSuppress;
  if (!sup) return false;
  if (sup.until < Date.now()) {
    window.entryClickSuppress = null;
    return false;
  }
  return true;
}

function setupEntryNoteModal() {
  const modal = document.getElementById("entry-note-modal");
  if (!modal || modal.dataset.bound === "true") return;
  const overlay = modal.querySelector(".entry-note-overlay");
  const content = document.getElementById("entry-note-content");

  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (content) content.innerHTML = "";
  };

  const openModal = () => {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  modal.addEventListener("click", (e) => {
    if (e.target.matches("[data-note-close]")) {
      closeModal();
    }
  });
  if (overlay) {
    overlay.addEventListener("click", closeModal);
  }
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  document.body.addEventListener("entry-note-saved", closeModal);

  window.openEntryNoteModal = (entryId) => {
    if (!content) return;
    openModal();
    content.innerHTML = "<div class=\"entry-note-card\"><p>Loading...</p></div>";
    if (typeof htmx !== "undefined") {
      htmx.ajax("GET", `/entries/${entryId}/note`, {
        target: "#entry-note-content",
        swap: "innerHTML",
      });
    }
  };

  modal.dataset.bound = "true";
}

function setupAddBlockModal() {
  const modal = document.getElementById("add-block-modal");
  const trigger = document.getElementById("add-block-btn");
  if (!modal || !trigger || modal.dataset.bound === "true") return;
  const form = document.getElementById("add-block-form");
  const closeTargets = modal.querySelectorAll("[data-block-close]");

  const openModal = () => {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    const firstInput = form ? form.querySelector("input[name='name']") : null;
    window.setTimeout(() => firstInput && firstInput.focus(), 10);
  };

  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  const handleSuccess = () => {
    if (form) {
      form.reset();
      // Reset icon picker to first icon
      const iconInput = form.querySelector("input[name='icon']");
      const iconOptions = form.querySelectorAll(".icon-option");
      if (iconInput && iconOptions.length > 0) {
        iconInput.value = iconOptions[0].dataset.icon;
        iconOptions.forEach((opt, i) => opt.classList.toggle("is-selected", i === 0));
      }
    }
    closeModal();
  };

  trigger.addEventListener("click", openModal);
  closeTargets.forEach((el) => el.addEventListener("click", closeModal));
  modal.addEventListener("click", (e) => {
    if (e.target === modal || e.target.matches("[data-block-close]")) {
      closeModal();
    }
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  // Listen for successful HTMX request from the add block form
  if (form) {
    form.addEventListener("htmx:afterRequest", (evt) => {
      if (evt.detail.successful) {
        handleSuccess();
      }
    });
  }

  modal.dataset.bound = "true";
}
