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

  function initQrSearch() {
    const startBtn = document.getElementById('qr-scanner-start');
    const stopBtn = document.getElementById('qr-scanner-stop');
    const wrap = document.getElementById('qr-scanner-wrap');
    const video = document.getElementById('qr-video');
    const input = document.getElementById('qr-code-input');
    const form = document.getElementById('qr-manual-form');

    if (!startBtn || !video || !form) return;

    let stream = null;
    let rafId = null;

    function stopCamera() {
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        stream = null;
      }
      video.srcObject = null;
      wrap.classList.add('hidden');
    }

    function submitCode(raw) {
      const code = parseCode(raw);
      if (!code) {
        window.alert('Не удалось распознать ID объекта.');
        return;
      }
      input.value = code;
      stopCamera();
      form.submit();
    }

    async function scanLoop(detector) {
      if (!stream) return;
      try {
        const codes = await detector.detect(video);
        if (codes.length > 0) {
          submitCode(codes[0].rawValue);
          return;
        }
      } catch (_err) {
        /* ignore frame errors */
      }
      rafId = requestAnimationFrame(() => scanLoop(detector));
    }

    async function startCamera() {
      if (!('BarcodeDetector' in window)) {
        window.alert('Сканер QR недоступен в этом браузере. Введите ID вручную.');
        return;
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        });
      } catch (_err) {
        window.alert('Не удалось открыть камеру. Проверьте разрешения.');
        return;
      }

      video.srcObject = stream;
      await video.play();
      wrap.classList.remove('hidden');

      const detector = new BarcodeDetector({ formats: ['qr_code'] });
      scanLoop(detector);
    }

    startBtn.addEventListener('click', startCamera);
    stopBtn.addEventListener('click', stopCamera);

    form.addEventListener('submit', (e) => {
      const code = parseCode(input.value);
      if (!code) {
        e.preventDefault();
        window.alert('Введите корректный ID (1–9999).');
      } else {
        input.value = code;
      }
    });
  }

  return {
    initPhotoSortable,
    initQrSearch,
  };
})();
