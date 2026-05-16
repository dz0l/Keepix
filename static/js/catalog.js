/* global KeepixCatalog */
const KeepixCatalog = (function () {
  'use strict';

  function parseCode(raw) {
    const match = String(raw || '').match(/\d{1,4}/);
    if (!match) return '';
    const num = parseInt(match[0], 10);
    if (num < 1 || num > 9999) return '';
    return String(num).padStart(4, '0');
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
        input.select();
      }, 0);
    }

    function closeModal() {
      modal.classList.add('hidden');
      document.body.classList.remove('modal-open');
    }

    if (openBtn) {
      openBtn.addEventListener('click', openModal);
    }

    modal.querySelectorAll('[data-qr-close]').forEach((el) => {
      el.addEventListener('click', closeModal);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
        closeModal();
      }
    });

    form.addEventListener('submit', (e) => {
      const code = parseCode(input.value);
      if (!code) {
        e.preventDefault();
        window.alert('Введите корректный ID (1–9999).');
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
      if (e.target.classList.contains('obj-select')) {
        syncSelectAllState();
      }
    });

    form.addEventListener('submit', (e) => {
      const checked = form.querySelectorAll('.obj-select:checked');
      if (!checked.length) {
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

    if (typeSelect) {
      typeSelect.addEventListener('change', () => form.submit());
    }

    if (search) {
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          form.submit();
        }
      });
    }
  }

  function initGlobal() {
    initQrModal();
    initBulkPrint();
    initCatalogFilters();
  }

  return {
    initPhotoSortable,
    initGlobal,
  };
})();
