document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-description-formset]');
  if (!root) return;

  const list = root.querySelector('[data-description-list]');
  const template = root.querySelector('[data-description-empty]');
  const total = root.querySelector('[name="descriptions-TOTAL_FORMS"]');
  const add = root.querySelector('[data-add-description]');
  if (!list || !template || !total || !add) return;

  const notify = () => document.dispatchEvent(new CustomEvent('jpc:variants-changed'));

  add.addEventListener('click', () => {
    const index = Number(total.value || 0);
    const html = template.innerHTML.replaceAll('__prefix__', String(index));
    list.insertAdjacentHTML('beforeend', html);
    total.value = String(index + 1);
    const row = list.lastElementChild;
    row?.querySelector('textarea')?.focus();
    notify();
  });

  root.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-description]');
    if (!button) return;
    const row = button.closest('[data-description-row]');
    if (!row) return;
    const deleteInput = row.querySelector('input[name$="-DELETE"]');
    if (deleteInput) deleteInput.checked = true;
    row.classList.add('is-deleted');
    notify();
  });

  root.addEventListener('input', notify);
  root.addEventListener('change', notify);
});
