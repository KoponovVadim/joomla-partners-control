function csrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}
async function post(url, options = {}) {
  const response = await fetch(url, {method: 'POST', headers: {'X-CSRFToken': csrfToken(), ...(options.headers || {})}, ...options});
  if (!response.ok) throw new Error('Ошибка запроса');
  return response.json();
}
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => { if (!confirm(form.dataset.confirm)) event.preventDefault(); }));
  document.querySelectorAll('[data-toggle-url]').forEach(input => input.addEventListener('change', async () => {
    input.disabled = true;
    try { const data = await post(input.dataset.toggleUrl); input.closest('.placement').classList.toggle('is-disabled', !data.enabled); }
    catch (_) { input.checked = !input.checked; alert('Не удалось изменить состояние'); }
    finally { input.disabled = false; }
  }));
  document.querySelectorAll('[data-remove-url]').forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Убрать клиента только с этого донора? Сам клиент останется в системе.')) return;
    try { await post(button.dataset.removeUrl); button.closest('.placement').remove(); } catch (_) { alert('Не удалось убрать размещение'); }
  }));
  document.querySelectorAll('.placement-list').forEach(list => {
    let dragged;
    list.querySelectorAll('[draggable=true]').forEach(item => {
      item.addEventListener('dragstart', () => { dragged = item; item.classList.add('dragging'); });
      item.addEventListener('dragend', async () => {
        item.classList.remove('dragging');
        const ids = [...list.querySelectorAll('[data-placement-id]')].map(el => Number(el.dataset.placementId));
        try { await post(list.dataset.reorderUrl, {headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids})}); } catch (_) { alert('Порядок не сохранён'); }
      });
      item.addEventListener('dragover', event => { event.preventDefault(); if (dragged !== item) { const box = item.getBoundingClientRect(); list.insertBefore(dragged, event.clientY < box.top + box.height / 2 ? item : item.nextSibling); } });
    });
  });

  const logoInput = document.querySelector('[data-logo-input]');
  const logoPreview = document.querySelector('[data-logo-preview]');
  const logoPreviewWrap = document.querySelector('[data-logo-preview-wrap]');
  if (logoInput && logoPreview && logoPreviewWrap) {
    let objectUrl = null;
    logoInput.addEventListener('change', () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      const file = logoInput.files?.[0];
      if (!file) return;
      objectUrl = URL.createObjectURL(file);
      logoPreview.src = objectUrl;
      logoPreviewWrap.hidden = false;
    });
  }

  const editor = document.querySelector('[name=default_html]');
  const liveFrame = document.querySelector('.live-preview iframe');
  if (editor && liveFrame) { const update = () => liveFrame.srcdoc = editor.value; editor.addEventListener('input', update); update(); }
  const previewSource = document.querySelector('#preview-source');
  const previewFrame = document.querySelector('#page-preview');
  if (previewSource && previewFrame) previewFrame.srcdoc = JSON.parse(previewSource.textContent);
  document.querySelectorAll('[data-source-tab]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-source-tab]').forEach(x => x.classList.toggle('active', x === button));
    document.querySelectorAll('[data-source]').forEach(x => x.hidden = x.dataset.source !== button.dataset.sourceTab);
  }));
});
