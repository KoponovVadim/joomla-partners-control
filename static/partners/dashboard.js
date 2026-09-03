document.addEventListener('DOMContentLoaded', () => {
  const items = [...document.querySelectorAll('[data-donor-item]')];
  const search = document.querySelector('[data-donor-search-input]');
  const status = document.querySelector('[data-donor-status-filter]');
  const empty = document.querySelector('[data-dashboard-no-results]');
  const expandedStorageKey = 'jpc-expanded-donors';
  const focusStorageKey = 'jpc-focus-donor';
  const clientPalette = [
    ['#3972a8', '#dceafa'],
    ['#43805c', '#dff0e4'],
    ['#9a6b21', '#f5e7c8'],
    ['#7056a1', '#e9e0f5'],
    ['#a25570', '#f4dde5'],
    ['#367b91', '#dceff3'],
    ['#75813c', '#e9edcf'],
    ['#a45f3d', '#f5dfd2'],
    ['#5268a0', '#e0e5f4'],
    ['#357e77', '#d9eeeb'],
    ['#875b83', '#efe0ec'],
    ['#5f7f4d', '#e3eddd'],
    ['#4f7188', '#dde8ef'],
    ['#8f6c35', '#efe3cf'],
    ['#96546e', '#f0dde7'],
    ['#477c68', '#dcefe7'],
  ];

  const hashClientKey = key => {
    let hash = 2166136261;
    for (let index = 0; index < key.length; index += 1) {
      hash ^= key.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

  const clientElements = [...document.querySelectorAll('[data-client-key]')];
  const clientKeys = [...new Set(
    clientElements
      .map(element => (element.dataset.clientKey || '').trim().toLowerCase())
      .filter(Boolean)
  )].sort((left, right) => {
    const hashDifference = hashClientKey(left) - hashClientKey(right);
    return hashDifference || left.localeCompare(right);
  });

  const paletteByClient = new Map();
  const usedPaletteIndexes = new Set();
  clientKeys.forEach(key => {
    const preferred = hashClientKey(key) % clientPalette.length;
    let paletteIndex = preferred;

    if (usedPaletteIndexes.size < clientPalette.length) {
      while (usedPaletteIndexes.has(paletteIndex)) {
        paletteIndex = (paletteIndex + 5) % clientPalette.length;
      }
      usedPaletteIndexes.add(paletteIndex);
    }

    paletteByClient.set(key, clientPalette[paletteIndex]);
  });

  clientElements.forEach(element => {
    const key = (element.dataset.clientKey || '').trim().toLowerCase();
    const color = paletteByClient.get(key);
    if (!color) return;
    const [accent, tint] = color;
    element.style.setProperty('--client-accent', accent);
    element.style.setProperty('--client-tint', tint);
  });

  let expandedDonors = new Set();
  try {
    expandedDonors = new Set(JSON.parse(sessionStorage.getItem(expandedStorageKey) || '[]'));
  } catch (error) {
    sessionStorage.removeItem(expandedStorageKey);
  }

  const persistExpandedDonors = () => {
    sessionStorage.setItem(expandedStorageKey, JSON.stringify([...expandedDonors]));
  };

  const setExpanded = (item, expanded) => {
    const button = item.querySelector('[data-donor-toggle]');
    const target = button ? document.getElementById(button.getAttribute('aria-controls')) : null;
    if (!button || !target) return;

    button.setAttribute('aria-expanded', String(expanded));
    target.hidden = !expanded;

    const donorId = item.dataset.donorId;
    if (!donorId) return;
    if (expanded) expandedDonors.add(donorId);
    else expandedDonors.delete(donorId);
    persistExpandedDonors();
  };

  const applyFilters = () => {
    if (!items.length) return;
    const needle = (search?.value || '').trim().toLowerCase();
    const selected = status?.value || 'all';
    let visible = 0;
    items.forEach(item => {
      const matchesText = !needle || (item.dataset.donorSearch || '').includes(needle);
      const matchesStatus = selected === 'all' || item.dataset.donorStatus === selected;
      const show = matchesText && matchesStatus;
      item.hidden = !show;
      if (show) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  };

  search?.addEventListener('input', applyFilters);
  status?.addEventListener('change', applyFilters);
  applyFilters();

  items.forEach(item => {
    const donorId = item.dataset.donorId;
    const button = item.querySelector('[data-donor-toggle]');
    if (!button) return;

    if (donorId && expandedDonors.has(donorId)) {
      setExpanded(item, true);
    }

    button.addEventListener('click', () => {
      setExpanded(item, button.getAttribute('aria-expanded') !== 'true');
    });
  });

  document.querySelectorAll('.add-placement').forEach(form => {
    form.addEventListener('submit', () => {
      const item = form.closest('[data-donor-id]');
      const donorId = item?.dataset.donorId;
      if (!donorId) return;
      expandedDonors.add(donorId);
      persistExpandedDonors();
      sessionStorage.setItem(focusStorageKey, donorId);
    });
  });

  const focusDonorId = sessionStorage.getItem(focusStorageKey);
  if (focusDonorId) {
    const item = items.find(candidate => candidate.dataset.donorId === focusDonorId);
    if (item) {
      setExpanded(item, true);
      window.requestAnimationFrame(() => {
        item.scrollIntoView({block: 'center'});
      });
    }
    sessionStorage.removeItem(focusStorageKey);
  }

  document.querySelectorAll('.placement [data-toggle-url]').forEach(input => {
    input.addEventListener('change', () => {
      const placement = input.closest('[data-placement-id]');
      if (!placement) return;
      const summary = document.querySelector(`[data-placement-summary-id="${placement.dataset.placementId}"]`);
      if (!summary) return;
      window.setTimeout(() => summary.classList.toggle('is-disabled', !input.checked), 250);
    });
  });
});
