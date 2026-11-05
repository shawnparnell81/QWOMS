'use strict';
// Single, consistent print action across QWOMS pages. This prints the currently
// visible application screen; original Excel/PDF files have their own print path.
(() => {
  const main = document.getElementById('main');
  const globalButton = document.getElementById('print-current-page');
  let prepared = false;
  let originalTitle = '';
  let banner = null;
  const values = [];

  function visible(element) {
    return !element.closest('[hidden], dialog:not([open]), .no-print, .hidden');
  }

  function printableValue(control) {
    const type = (control.type || '').toLowerCase();
    if (type === 'password' || type === 'hidden' || type === 'file' ||
        type === 'submit' || type === 'button' || type === 'reset') return null;
    if (type === 'checkbox' || type === 'radio') return control.checked ? '✓' : '☐';
    if (control.tagName === 'SELECT') {
      return Array.from(control.selectedOptions).map(option => option.textContent).join(', ');
    }
    return control.value || '—';
  }

  function preparePrint() {
    if (prepared || !main || document.getElementById('shell')?.classList.contains('hidden')) return;
    prepared = true;
    originalTitle = document.title;
    const title = main.querySelector('h1')?.textContent?.trim() ||
      document.getElementById('crumb')?.textContent?.trim() || 'Quality work';
    document.title = 'QWOMS — ' + title;
    banner = document.createElement('div');
    banner.className = 'print-document-heading';
    const kicker = document.createElement('div');
    kicker.className = 'print-document-brand';
    kicker.textContent = 'QWOMS  /  QUALITY WORK ORDER MANAGEMENT';
    const heading = document.createElement('h1');
    heading.textContent = title;
    const meta = document.createElement('div');
    meta.className = 'print-document-meta';
    meta.textContent = 'Printed ' + new Date().toLocaleString() +
      '  ·  ' + (document.getElementById('user-name')?.textContent || 'Authorized user');
    banner.append(kicker, heading, meta);
    main.prepend(banner);

    // Browser print engines clip input contents. Display the current form values
    // as normal text on paper without modifying the saved work order or form.
    for (const control of main.querySelectorAll('input, select, textarea')) {
      if (!visible(control)) continue;
      const value = printableValue(control);
      if (value === null) continue;
      const snapshot = document.createElement('span');
      snapshot.className = 'print-field-value';
      snapshot.textContent = value;
      control.classList.add('print-value-source');
      control.after(snapshot);
      values.push({control, snapshot});
    }
    document.body.classList.add('print-ready');
  }

  function restorePrint() {
    if (!prepared) return;
    document.title = originalTitle;
    for (const {control, snapshot} of values) {
      control.classList.remove('print-value-source');
      snapshot.remove();
    }
    values.length = 0;
    banner?.remove();
    banner = null;
    prepared = false;
    document.body.classList.remove('print-ready');
  }

  function printCurrentPage() {
    if (document.getElementById('shell')?.classList.contains('hidden')) return;
    preparePrint();
    window.print();
    // The normal afterprint event restores the live form. A timeout is not used
    // because a delayed cleanup can erase content during the print preview.
  }

  globalButton?.addEventListener('click', printCurrentPage);
  document.addEventListener('click', event => {
    const control = event.target.closest('[data-print-page]');
    if (!control) return;
    event.preventDefault();
    printCurrentPage();
  });
  window.addEventListener('beforeprint', preparePrint);
  window.addEventListener('afterprint', restorePrint);
})();
