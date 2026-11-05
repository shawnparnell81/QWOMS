'use strict';
// Recoverable audited work-order deletion. Nothing is permanently erased.
(() => {
  const modal = document.createElement('dialog');
  modal.className = 'archive-dialog no-print';
  modal.setAttribute('aria-labelledby','archive-dialog-title');
  modal.innerHTML =
    '<form id="archive-order-form" class="archive-dialog-form">'+
      '<div class="archive-dialog-header"><div><p class="eyebrow">WORK ORDER HISTORY</p><h2 id="archive-dialog-title">Delete work order</h2></div><button type="button" class="plain-btn" id="archive-dialog-close" aria-label="Close">×</button></div>'+
      '<p id="archive-dialog-info" class="muted"></p>'+
      '<div class="alert warn" id="archive-dialog-note"></div>'+
      '<label>Type the exact work order number to confirm<input name="confirm_number" required autocomplete="off" spellcheck="false"></label>'+
      '<label>Reason for this action<textarea name="reason" required minlength="8" maxlength="2000" placeholder="Explain why this work order is being removed from active work"></textarea></label>'+
      '<p role="alert" id="archive-dialog-error" class="error"></p>'+
      '<div class="archive-dialog-actions"><button type="button" id="archive-cancel" class="btn">Keep work order</button><button type="submit" class="btn primary" id="archive-submit">Delete work order</button></div>'+
    '</form>';
  document.body.append(modal);
  const form = modal.querySelector('form');
  const info = modal.querySelector('#archive-dialog-info');
  const note = modal.querySelector('#archive-dialog-note');
  const title = modal.querySelector('#archive-dialog-title');
  const submit = modal.querySelector('#archive-submit');
  const error = modal.querySelector('#archive-dialog-error');
  let target = null;

  function open(button, mode) {
    if (mode !== 'cancel' && !state?.me?.is_admin) return;
    if (mode === 'cancel' && !state?.me?.is_admin && !['Quality','Engineering','Management'].includes(state.me.role))return;
    target = {id: Number(button.dataset.restoreOrder || button.dataset.archiveOrder || button.dataset.cancelOrder),
      number: button.dataset.orderNumber, mode};
    form.reset();
    error.textContent='';
    const restoring=mode==='restore', cancelling=mode==='cancel';
    title.textContent = restoring ? 'Restore archived work order' : cancelling ? 'Cancel work order' : 'Delete work order';
    info.textContent = (restoring ? 'Restore ' : cancelling ? 'Cancel ' : 'Delete ') + target.number + '?';
    note.textContent = restoring
      ? 'Restore the original work order with its saved number, history, drawings and attached evidence.'
      : cancelling
        ? 'The work order will be marked Cancelled and removed from active assignments. Its number, drawings, forms, labor and history remain recorded.'
        : 'This is recoverable deletion, not permanent erasure. The order leaves active lists but its number, documents, completed forms, labor and audit records remain.';
    submit.textContent = restoring ? 'Restore work order' : cancelling ? 'Cancel work order' : 'Delete work order';
    submit.classList.toggle('archive-danger', !restoring);
    modal.showModal();
    form.elements.confirm_number.focus();
  }
  modal.querySelector('#archive-dialog-close').onclick=()=>modal.close();
  modal.querySelector('#archive-cancel').onclick=()=>modal.close();
  modal.addEventListener('click', event => {if(event.target===modal)modal.close()});
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-archive-order],[data-restore-order],[data-cancel-order]');
    if(!button)return;
    event.preventDefault();event.stopPropagation();
    open(button,button.hasAttribute('data-restore-order')?'restore':button.hasAttribute('data-cancel-order')?'cancel':'archive');
  },true);
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!target)return;
    const number=form.elements.confirm_number.value;
    const reason=form.elements.reason.value.trim();
    if(number!==target.number){error.textContent='The number must exactly match '+target.number;return}
    if(reason.length<8){error.textContent='Enter a specific reason (at least 8 characters).';return}
    submit.disabled=true;error.textContent='';
    try{
      const action=target.mode==='restore'?'restore':target.mode==='cancel'?'cancel':'archive';
      await api('/api/work-orders/'+target.id+'/'+action,{method:'POST',body:{confirm_number:number,reason}});
      const restored=target.mode==='restore';
      const cancelled=target.mode==='cancel';
      modal.close();
      state.orderFilter=restored?'archived':'all';
      await navigate('orders');
      toast(restored?'Work order restored; history preserved.':cancelled?'Work order cancelled; record and history preserved.':'Work order deleted from active lists; archived history preserved.');
    }catch(err){error.textContent=err.message||'Unable to update this work order'}
    finally{submit.disabled=false}
  });
})();