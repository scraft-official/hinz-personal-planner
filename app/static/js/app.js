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
    setupRecurringTaskModal();
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
  setupRecurringTaskModal();
  setupRecurringConfirmModal();
  setupConfirmDialog();
  setupThemeToggle();
}

/* ---------- TOUCH HELPERS ---------- */
function isTouchDevice() {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}

function getEventCoords(e) {
  if (e.touches && e.touches.length > 0) {
    return { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
  }
  if (e.changedTouches && e.changedTouches.length > 0) {
    return { clientX: e.changedTouches[0].clientX, clientY: e.changedTouches[0].clientY };
  }
  return { clientX: e.clientX, clientY: e.clientY };
}

function addDragListeners() {
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", onDragEnd);
  window.addEventListener("touchmove", onDragMove, { passive: false });
  window.addEventListener("touchend", onDragEnd);
  window.addEventListener("touchcancel", onDragEnd);
}

function removeDragListeners() {
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", onDragEnd);
  window.removeEventListener("touchmove", onDragMove);
  window.removeEventListener("touchend", onDragEnd);
  window.removeEventListener("touchcancel", onDragEnd);
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
      if (blockId) {
        window.openConfirmDialog(
          "Delete Block Type",
          "Delete this block type? All entries using it will also be deleted.",
          () => {
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
        );
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
    card.addEventListener("touchstart", (e) => {
      if (e.target.closest(".palette-delete-btn")) return;
      e.preventDefault();
      startPaletteDrag(e, card);
    }, { passive: false });
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
  addDragListeners();
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
    const recurringTaskId = btn.dataset.recurringTaskId;
    const instanceDate = btn.dataset.instanceDate;
    const weekStart = getWeekStart();

    // Prevent double-click issues
    if (btn.disabled) return;

    if (recurringTaskId) {
      // This is a recurring task - show confirmation dialog
      window.openRecurringConfirm(
        "Do you want to delete only this instance or all occurrences?",
        // Delete single instance
        () => {
          btn.disabled = true;
          const formData = new FormData();
          formData.append("exception_date", instanceDate);
          formData.append("exception_type", "deleted");
          if (weekStart) formData.append("week", weekStart);

          fetch(`/recurring-tasks/${recurringTaskId}/exception`, {
            method: "POST",
            headers: { "HX-Request": "true" },
            body: formData,
          })
            .then((r) => r.text())
            .then(replaceScheduleHtml)
            .catch(console.error);
        },
        // Delete all instances
        () => {
          btn.disabled = true;
          let url = `/recurring-tasks/${recurringTaskId}`;
          if (weekStart) url += `?week=${weekStart}`;

          fetch(url, {
            method: "DELETE",
            headers: { "HX-Request": "true" },
          })
            .then((r) => r.text())
            .then(replaceScheduleHtml)
            .catch(console.error);
        }
      );
    } else if (entryId) {
      // Regular entry - delete directly
      btn.disabled = true;
      let url = `/entries/${entryId}`;
      if (weekStart) url += `?week_start=${weekStart}`;

      fetch(url, {
        method: "DELETE",
        headers: { "HX-Request": "true" },
      })
        .then((r) => r.text())
        .then(replaceScheduleHtml)
        .catch(console.error);
    }
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

    // Touch support for entries
    let touchStartTimer = null;
    entry.addEventListener("touchstart", (e) => {
      if (e.target.closest(".entry-delete-btn")) return;
      if (e.target.closest(".entry-title-text")) return;
      
      if (e.target.closest(".entry-resize-handle")) {
        e.preventDefault();
        e.stopPropagation();
        startResize(e, entry, meta);
        return;
      }
      
      // Start drag immediately for touch
      e.preventDefault();
      startEntryDrag(e, entry, meta);
    }, { passive: false });

    entry.addEventListener("click", (e) => handleEntryClick(e, entry));
  });
}

function startEntryDrag(event, entry, meta) {
  window.dragState = {
    mode: "move",
    entry,
    id: entry.dataset.entryId,
    recurringTaskId: entry.dataset.recurringTaskId,
    instanceDate: entry.dataset.instanceDate,
    isRecurring: entry.dataset.isRecurring === "true",
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
  addDragListeners();
}

function startResize(event, entry, meta) {
  window.dragState = {
    mode: "resize",
    entry,
    id: entry.dataset.entryId,
    recurringTaskId: entry.dataset.recurringTaskId,
    instanceDate: entry.dataset.instanceDate,
    isRecurring: entry.dataset.isRecurring === "true",
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
  addDragListeners();
}

/* ---------- COLLISION DETECTION ---------- */
function getEntriesInCol(col, excludeInfo) {
  const entries = col.querySelectorAll(".entry");
  const result = [];
  entries.forEach((entry) => {
    const id = entry.dataset.entryId;
    const recurringTaskId = entry.dataset.recurringTaskId;
    const instanceDate = entry.dataset.instanceDate;
    
    // Exclude the entry being dragged
    if (excludeInfo) {
      if (excludeInfo.entryId && id === String(excludeInfo.entryId)) return;
      // For recurring tasks, exclude by recurring task ID and instance date
      if (excludeInfo.recurringTaskId && 
          recurringTaskId === String(excludeInfo.recurringTaskId) && 
          instanceDate === excludeInfo.instanceDate) return;
    }
    
    result.push({
      id,
      recurringTaskId,
      instanceDate,
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

  // Prevent default for touch events to avoid scrolling
  if (event.cancelable) event.preventDefault();

  const coords = getEventCoords(event);
  const col = findDayCol(coords.clientX, coords.clientY);
  if (!col) {
    ds.indicator.style.display = "none";
    ds.target = null;
    return;
  }
  ds.indicator.style.display = "";

  const { meta, mode } = ds;
  const rect = col.getBoundingClientRect();
  const y = Math.max(0, coords.clientY - rect.top);
  
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
  let excludeInfo = null;
  if (mode === "move" || mode === "resize") {
    excludeInfo = {
      entryId: ds.id,
      recurringTaskId: ds.recurringTaskId,
      instanceDate: ds.instanceDate,
    };
  }
  const existingEntries = getEntriesInCol(col, excludeInfo);
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
  removeDragListeners();

  // Always suppress click after any drag operation
  suppressEntryClick();

  if (!ds.target) {
    window.dragState = null;
    return;
  }

  const { target, mode } = ds;
  const weekStart = getWeekStart();

  if (mode === "move" || mode === "resize") {
    if (ds.isRecurring) {
      // Recurring task - show confirmation dialog
      const newDayOfWeek = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].indexOf(target.day);
      
      window.openRecurringConfirm(
        "Do you want to change only this instance or all occurrences?",
        // Change single instance
        () => {
          const fd = new FormData();
          fd.append("exception_date", ds.instanceDate);
          fd.append("exception_type", "modified");
          fd.append("new_day", target.day);
          fd.append("new_start_minute", String(target.startMinute));
          fd.append("new_duration_minutes", String(target.duration));
          if (weekStart) fd.append("week", weekStart);

          fetch(`/recurring-tasks/${ds.recurringTaskId}/exception`, {
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
        },
        // Change all instances
        () => {
          const fd = new FormData();
          fd.append("day_of_week", String(newDayOfWeek));
          fd.append("start_minute", String(target.startMinute));
          fd.append("duration_minutes", String(target.duration));
          if (weekStart) fd.append("week", weekStart);
          // Clear any exception for the instance being dragged so it reflects the new base values
          if (ds.instanceDate) fd.append("clear_exception_date", ds.instanceDate);

          fetch(`/recurring-tasks/${ds.recurringTaskId}/move-all`, {
            method: "PATCH",
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
      );
    } else {
      // Regular entry
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
    }
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
    // Get or create error message element
    let errorEl = form.querySelector(".quick-task-error");
    if (!errorEl) {
      errorEl = document.createElement("div");
      errorEl.className = "quick-task-error";
      form.insertBefore(errorEl, form.firstChild);
    }
    
    form.addEventListener("htmx:afterRequest", (evt) => {
      if (evt.detail.successful) {
        errorEl.textContent = "";
        errorEl.style.display = "none";
        handleSuccess();
      } else if (evt.detail.xhr && evt.detail.xhr.status === 409) {
        // Collision detected - time slot occupied
        errorEl.textContent = "This time slot is already occupied. Please choose a different time.";
        errorEl.style.display = "block";
      }
    });
    
    // Clear error when form inputs change
    form.addEventListener("input", () => {
      errorEl.textContent = "";
      errorEl.style.display = "none";
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
  if (isEntryClickSuppressed()) return;
  event.preventDefault();
  event.stopPropagation();

  const entryId = titleText.dataset.entryId;
  const recurringTaskId = titleText.dataset.recurringTaskId;
  const instanceDate = titleText.dataset.instanceDate;

  if (recurringTaskId) {
    // Recurring task - open recurring note modal
    if (typeof openRecurringNoteModal === "function") {
      openRecurringNoteModal(recurringTaskId, instanceDate);
    }
  } else if (entryId) {
    // Regular entry
    if (typeof openEntryNoteModal === "function") {
      openEntryNoteModal(entryId);
    }
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
    // Handle delete entry button
    const deleteEntryBtn = e.target.closest("[data-delete-entry]");
    if (deleteEntryBtn) {
      const entryId = deleteEntryBtn.dataset.deleteEntry;
      if (entryId) {
        // Use custom confirm dialog
        window.openConfirmDialog(
          "Delete Entry",
          "Are you sure you want to delete this entry?",
          () => {
            const weekStart = getWeekStart();
            let url = `/entries/${entryId}`;
            if (weekStart) url += `?week_start=${weekStart}`;
            fetch(url, {
              method: "DELETE",
              headers: { "HX-Request": "true" },
            })
              .then((r) => r.text())
              .then((html) => {
                replaceScheduleHtml(html);
                closeModal();
              })
              .catch(console.error);
          }
        );
      }
    }
    // Handle delete recurring task button
    const deleteRecurringBtn = e.target.closest("[data-delete-recurring]");
    if (deleteRecurringBtn) {
      const taskId = deleteRecurringBtn.dataset.deleteRecurring;
      const instanceDate = deleteRecurringBtn.dataset.instanceDate;
      if (taskId) {
        // Use recurring confirm dialog for delete options
        window.openRecurringConfirm(
          "Do you want to delete only this instance or all occurrences?",
          // Delete single instance
          () => {
            const weekStart = getWeekStart();
            const fd = new FormData();
            fd.append("exception_date", instanceDate);
            fd.append("exception_type", "deleted");
            if (weekStart) fd.append("week", weekStart);

            fetch(`/recurring-tasks/${taskId}/exception`, {
              method: "POST",
              headers: { "HX-Request": "true" },
              body: fd,
            })
              .then((r) => r.text())
              .then((html) => {
                replaceScheduleHtml(html);
                closeModal();
              })
              .catch(console.error);
          },
          // Delete all instances
          () => {
            const weekStart = getWeekStart();
            let url = `/recurring-tasks/${taskId}`;
            if (weekStart) url += `?week_start=${weekStart}`;
            fetch(url, {
              method: "DELETE",
              headers: { "HX-Request": "true" },
            })
              .then((r) => r.text())
              .then((html) => {
                replaceScheduleHtml(html);
                closeModal();
              })
              .catch(console.error);
          }
        );
      }
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

  window.openRecurringNoteModal = (taskId, instanceDate) => {
    if (!content) return;
    openModal();
    content.innerHTML = "<div class=\"entry-note-card\"><p>Loading...</p></div>";
    if (typeof htmx !== "undefined") {
      let url = `/recurring-tasks/${taskId}/note`;
      if (instanceDate) url += `?instance_date=${instanceDate}`;
      htmx.ajax("GET", url, {
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

/* ---------- RECURRING TASK MODAL ---------- */
function setupRecurringTaskModal() {
  const modal = document.getElementById("recurring-task-modal");
  const trigger = document.getElementById("recurring-task-btn");
  if (!modal || !trigger || modal.dataset.bound === "true") return;
  const form = document.getElementById("recurring-task-form");
  const closeTargets = modal.querySelectorAll("[data-recurring-close]");
  const patternSelect = document.getElementById("recurring-pattern");
  const dayOfWeekLabel = document.getElementById("day-of-week-label");
  const dayOfMonthLabel = document.getElementById("day-of-month-label");

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
    closeModal();
  };

  // Toggle day picker based on pattern
  const updateDayPicker = () => {
    const pattern = patternSelect ? patternSelect.value : "weekly";
    if (dayOfWeekLabel) dayOfWeekLabel.style.display = (pattern === "weekly") ? "grid" : "none";
    if (dayOfMonthLabel) dayOfMonthLabel.style.display = (pattern === "monthly") ? "grid" : "none";
  };

  if (patternSelect) {
    patternSelect.addEventListener("change", updateDayPicker);
    updateDayPicker();
  }

  trigger.addEventListener("click", openModal);
  closeTargets.forEach((el) => el.addEventListener("click", closeModal));
  modal.addEventListener("click", (e) => {
    if (e.target === modal || e.target.matches("[data-recurring-close]")) {
      closeModal();
    }
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  if (form) {
    form.addEventListener("htmx:afterRequest", (evt) => {
      if (evt.detail.successful) {
        handleSuccess();
      }
    });
  }

  modal.dataset.bound = "true";
}

/* ---------- RECURRING CONFIRM MODAL ---------- */
let recurringConfirmState = null;

function setupRecurringConfirmModal() {
  const modal = document.getElementById("recurring-confirm-modal");
  if (!modal || modal.dataset.bound === "true") return;
  
  const closeTargets = modal.querySelectorAll("[data-confirm-close]");
  const singleBtn = document.getElementById("recurring-confirm-single");
  const allBtn = document.getElementById("recurring-confirm-all");
  const messageEl = document.getElementById("recurring-confirm-message");

  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    recurringConfirmState = null;
  };

  closeTargets.forEach((el) => el.addEventListener("click", closeModal));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  if (singleBtn) {
    singleBtn.addEventListener("click", () => {
      if (recurringConfirmState && recurringConfirmState.onSingle) {
        recurringConfirmState.onSingle();
      }
      closeModal();
    });
  }

  if (allBtn) {
    allBtn.addEventListener("click", () => {
      if (recurringConfirmState && recurringConfirmState.onAll) {
        recurringConfirmState.onAll();
      }
      closeModal();
    });
  }

  window.openRecurringConfirm = (message, onSingle, onAll) => {
    if (messageEl) messageEl.textContent = message;
    recurringConfirmState = { onSingle, onAll };
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  modal.dataset.bound = "true";
}

/* ---------- GENERIC CONFIRM DIALOG ---------- */
let confirmDialogState = null;

function setupConfirmDialog() {
  const modal = document.getElementById("confirm-modal");
  if (!modal || modal.dataset.bound === "true") return;
  
  const closeTargets = modal.querySelectorAll("[data-generic-confirm-close]");
  const okBtn = document.getElementById("confirm-ok");
  const titleEl = document.getElementById("confirm-title");
  const messageEl = document.getElementById("confirm-message");

  const closeModal = () => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    confirmDialogState = null;
  };

  closeTargets.forEach((el) => el.addEventListener("click", closeModal));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });

  if (okBtn) {
    okBtn.addEventListener("click", () => {
      if (confirmDialogState && confirmDialogState.onConfirm) {
        confirmDialogState.onConfirm();
      }
      closeModal();
    });
  }

  window.openConfirmDialog = (title, message, onConfirm) => {
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;
    confirmDialogState = { onConfirm };
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  modal.dataset.bound = "true";
}

/* ─────────────────────────────────────────────────────────
   Import button handler
───────────────────────────────────────────────────────── */
(function setupImport() {
  const importBtn = document.getElementById("import-btn");
  const importFile = document.getElementById("import-file");
  
  if (!importBtn || !importFile) return;
  if (importBtn.dataset.bound) return;
  
  importBtn.addEventListener("click", () => {
    importFile.click();
  });
  
  importFile.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Confirm before import
    window.openConfirmDialog(
      "Import Data",
      "This will replace ALL existing data. Are you sure?",
      async () => {
        const fd = new FormData();
        fd.append("file", file);
        
        try {
          const resp = await fetch("/import/csv", {
            method: "POST",
            body: fd,
          });
          
          if (resp.ok) {
            window.location.href = "/";
          } else {
            const text = await resp.text();
            alert("Import failed: " + text);
          }
        } catch (err) {
          alert("Import error: " + err.message);
        }
        
        // Reset file input
        importFile.value = "";
      }
    );
    
    // If user cancels, reset file input
    setTimeout(() => {
      if (!document.querySelector(".confirm-modal.is-open")) {
        importFile.value = "";
      }
    }, 100);
  });
  
  importBtn.dataset.bound = "true";
})();

