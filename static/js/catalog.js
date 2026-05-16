/* global KeepixCatalog */
const KeepixCatalog = (function () {
  'use strict';

  const THEME_KEY = 'keepix-theme';
  const THEME_CYCLE = ['dark', 'light', 'system'];

  function parseCode(raw) {
    const text = String(raw || '').trim();
    if (!text) return '';

    const urlMatch = text.match(/\/objects\/(\d{1,4})(?:\/|[\s?#]|$)/i);
    if (urlMatch) {
      const num = parseInt(urlMatch[1], 10);
      if (num >= 1 && num <= 9999) return String(num).padStart(4, '0');
    }

    const idMatch = text.match(/(?:^|\n)\s*ID\s*:\s*(\d{1,4})\s*(?:$|\n)/i);
    if (idMatch) {
      const num = parseInt(idMatch[1], 10);
      if (num >= 1 && num <= 9999) return String(num).padStart(4, '0');
    }

    const compact = text.replace(/\s+/g, '');
    if (/^\d{1,4}$/.test(compact)) {
      const num = parseInt(compact, 10);
      if (num >= 1 && num <= 9999) return String(num).padStart(4, '0');
    }

    if (text.length <= 16 && !/\d+\.\d+/.test(text)) {
      const match = text.match(/\b(\d{1,4})\b/);
      if (match) {
        const num = parseInt(match[1], 10);
        if (num >= 1 && num <= 9999) return String(num).padStart(4, '0');
      }
    }

    return '';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
      const labels = { dark: 'Тёмная', light: 'Светлая', system: 'Системная' };
      btn.title = `Тема: ${labels[theme] || theme}`;
    }
  }

  function initTheme() {
    let theme = localStorage.getItem(THEME_KEY) || 'dark';
    if (!THEME_CYCLE.includes(theme)) theme = 'dark';
    applyTheme(theme);

    const btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;

    btn.addEventListener('click', () => {
      const current = localStorage.getItem(THEME_KEY) || 'dark';
      const idx = THEME_CYCLE.indexOf(current);
      const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  }

  function initPhotoSortable() {
    const list = document.getElementById('photo-sortable');
    const orderInput = document.getElementById('photo-order');
    if (!list || !orderInput) return;

    let dragged = null;

    function syncOrder() {
      const ids = Array.from(list.querySelectorAll('[data-photo-id]')).map(
        (el) => el.getAttribute('data-photo-id'),
      );
      orderInput.value = ids.join(',');
    }

    list.addEventListener('dragstart', (e) => {
      const tile = e.target.closest('[data-photo-id]');
      if (!tile) return;
      dragged = tile;
      tile.classList.add('dragging');
    });

    list.addEventListener('dragend', () => {
      if (dragged) dragged.classList.remove('dragging');
      dragged = null;
      syncOrder();
    });

    list.addEventListener('dragover', (e) => {
      e.preventDefault();
      const tile = e.target.closest('[data-photo-id]');
      if (!tile || !dragged || tile === dragged) return;
      const rect = tile.getBoundingClientRect();
      const after = e.clientX > rect.left + rect.width / 2;
      list.insertBefore(dragged, after ? tile.nextSibling : tile);
    });

    syncOrder();
  }

  function assignFiles(input, files) {
    const dt = new DataTransfer();
    Array.from(files).forEach((file) => dt.items.add(file));
    input.files = dt.files;
  }

  function renderDropzoneList(input) {
    const list = document.querySelector(`[data-dropzone-list="${input.id}"]`);
    if (!list) return;
    list.innerHTML = '';
    if (!input.files.length) {
      list.hidden = true;
      return;
    }
    Array.from(input.files).forEach((file) => {
      const li = document.createElement('li');
      li.textContent = file.name;
      list.appendChild(li);
    });
    list.hidden = false;
  }

  function initFileDropzones() {
    document.querySelectorAll('[data-dropzone-for]').forEach((zone) => {
      const inputId = zone.getAttribute('data-dropzone-for');
      const input = document.getElementById(inputId);
      if (!input) return;

      input.classList.add('drop-input-hidden');

      ['dragenter', 'dragover'].forEach((evt) => {
        zone.addEventListener(evt, (e) => {
          e.preventDefault();
          zone.classList.add('dropzone-active');
        });
      });

      ['dragleave', 'drop'].forEach((evt) => {
        zone.addEventListener(evt, (e) => {
          e.preventDefault();
          zone.classList.remove('dropzone-active');
        });
      });

      zone.addEventListener('drop', (e) => {
        const dropped = e.dataTransfer?.files;
        if (!dropped?.length) return;
        assignFiles(input, dropped);
        renderDropzoneList(input);
      });

      input.addEventListener('change', () => renderDropzoneList(input));
    });
  }

  function initQrModal() {
    const modal = document.getElementById('qr-modal');
    const openBtn = document.getElementById('qr-open-btn');
    const form = document.getElementById('qr-modal-form');
    const input = document.getElementById('qr-code-input');
    if (!modal || !form || !input) return;

    function openModal() {
      modal.classList.remove('hidden');
      document.body.classList.add('modal-open');
      window.setTimeout(() => {
        input.value = '';
        input.focus();
      }, 0);
    }

    function closeModal() {
      modal.classList.add('hidden');
      document.body.classList.remove('modal-open');
    }

    if (openBtn) openBtn.addEventListener('click', openModal);

    modal.querySelectorAll('[data-qr-close]').forEach((el) => {
      el.addEventListener('click', closeModal);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
    });

    form.addEventListener('submit', (e) => {
      const code = parseCode(input.value);
      if (!code) {
        e.preventDefault();
        window.alert('Не удалось определить ID объекта.');
        return;
      }
      input.value = code;
    });

    if (new URLSearchParams(window.location.search).get('qr') === '1') {
      openModal();
      const url = new URL(window.location.href);
      url.searchParams.delete('qr');
      window.history.replaceState({}, '', url);
    }
  }

  function initBulkPrint() {
    const selectAll = document.getElementById('select-all-objects');
    const form = document.getElementById('catalog-list-form');
    if (!selectAll || !form) return;

    function getCheckboxes() {
      return form.querySelectorAll('.obj-select');
    }

    function syncSelectAllState() {
      const boxes = getCheckboxes();
      if (!boxes.length) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
        return;
      }
      const checked = Array.from(boxes).filter((cb) => cb.checked).length;
      selectAll.checked = checked === boxes.length;
      selectAll.indeterminate = checked > 0 && checked < boxes.length;
    }

    selectAll.addEventListener('change', () => {
      const checked = selectAll.checked;
      getCheckboxes().forEach((cb) => {
        cb.checked = checked;
      });
      selectAll.indeterminate = false;
    });

    form.addEventListener('change', (e) => {
      if (e.target.classList.contains('obj-select')) syncSelectAllState();
    });

    form.addEventListener('submit', (e) => {
      if (!form.querySelectorAll('.obj-select:checked').length) {
        e.preventDefault();
        window.alert('Выберите хотя бы один объект для печати.');
      }
    });

    syncSelectAllState();
  }

  function initCatalogFilters() {
    const form = document.getElementById('catalog-filter-form');
    if (!form) return;

    const search = form.querySelector('.filter-search');
    const typeSelect = form.querySelector('.filter-type');

    if (typeSelect) typeSelect.addEventListener('change', () => form.submit());

    if (search) {
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          form.submit();
        }
      });
    }
  }

  function initPhotoLightbox() {
    const modal = document.getElementById('photo-lightbox');
    const image = document.getElementById('lightbox-image');
    const prevBtn = modal?.querySelector('.lightbox-prev');
    const nextBtn = modal?.querySelector('.lightbox-next');
    const triggers = document.querySelectorAll('.photo-lightbox-open');
    if (!modal || !image || !triggers.length) return;

    const sources = Array.from(triggers).map((el) => el.getAttribute('data-lightbox-src'));
    let index = 0;

    function show(idx) {
      index = (idx + sources.length) % sources.length;
      image.src = sources[index];
      const multi = sources.length > 1;
      if (prevBtn) prevBtn.hidden = !multi;
      if (nextBtn) nextBtn.hidden = !multi;
    }

    function openAt(idx) {
      show(idx);
      modal.classList.remove('hidden');
      document.body.classList.add('modal-open');
    }

    function close() {
      modal.classList.add('hidden');
      document.body.classList.remove('modal-open');
      image.src = '';
    }

    triggers.forEach((btn, idx) => {
      btn.addEventListener('click', () => openAt(idx));
    });

    modal.querySelectorAll('[data-lightbox-close]').forEach((el) => {
      el.addEventListener('click', close);
    });

    if (prevBtn) prevBtn.addEventListener('click', () => show(index - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => show(index + 1));

    document.addEventListener('keydown', (e) => {
      if (modal.classList.contains('hidden')) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(index - 1);
      if (e.key === 'ArrowRight') show(index + 1);
    });
  }

  function initGlobal() {
    initTheme();
    initQrModal();
    initBulkPrint();
    initCatalogFilters();
  }

  return {
    initPhotoSortable,
    initFileDropzones,
    initPhotoLightbox,
    initGlobal,
  };
})();
