'use strict';
// Edit only safe metadata and fields of the work order's actual type.
// Part aliases, quantities and pinned revisions are intentionally unchanged.
(() => {
  const dialog=document.createElement('dialog');
  dialog.className='archive-dialog edit-dialog no-print';
  dialog.setAttribute('aria-labelledby','edit-order-title');
  dialog.innerHTML=
    '<form id="edit-order-form" class="archive-dialog-form">'+
      '<div class="archive-dialog-header"><div><p class="eyebrow">WORK ORDER</p><h2 id="edit-order-title">Edit work order</h2></div><button type="button" class="plain-btn" id="edit-close" aria-label="Close">×</button></div>'+
      '<p class="muted" id="edit-order-number"></p>'+
      '<label>Work order description<input name="title" required minlength="3" maxlength="250"></label>'+
      '<label>Priority<select name="priority"><option>Low</option><option>Normal</option><option>High</option><option>Urgent</option></select></label>'+
      '<div id="edit-type-fields"></div>'+
      '<label>Additional notes<textarea name="notes" maxlength="10000"></textarea></label>'+
      '<div class="alert info">Part numbers, quantities, controlled drawing revisions and previously completed files are not modified by this editor. Those changes require a separate controlled review.</div>'+
      '<p role="alert" id="edit-order-error" class="error"></p>'+
      '<div class="archive-dialog-actions"><button type="button" class="btn" id="edit-cancel">Discard changes</button><button type="submit" class="btn primary" id="edit-save">Save work order</button></div>'+
    '</form>';
  document.body.append(dialog);
  const form=dialog.querySelector('form');
  const dynamic=dialog.querySelector('#edit-type-fields');
  const error=dialog.querySelector('#edit-order-error');
  const submit=dialog.querySelector('#edit-save');
  let current=null;

  function editable(entry){
    return entry&&!entry.archived&&!['Completed','Closed','Cancelled'].includes(entry.status);
  }
  async function open(id){
    error.textContent='';
    let order;
    try{order=await api('/api/work-orders/'+id)}
    catch(e){toast(e.message);return}
    if(!editable(order)){toast('This work order is read-only');return}
    if(!(state.me.is_admin||['Quality','Engineering','Management'].includes(state.me.role))){
      toast('You do not have permission to edit this work order');return
    }
    current=order;
    form.reset();
    dialog.querySelector('#edit-order-number').textContent=order.number+' · '+order.order_type+' / '+order.subtype;
    form.elements.title.value=order.title||'';
    form.elements.priority.value=order.priority||'Normal';
    form.elements.notes.value=order.notes||'';
    dynamic.replaceChildren();
    const fields=state.types?.[order.order_type]?.fields||Object.keys(order.details||{});
    if(fields.length){
      const header=document.createElement('p');
      header.className='section-kicker';
      header.textContent=order.order_type+' details';
      dynamic.append(header);
      for(const key of fields){
        const label=document.createElement('label');
        label.className='edit-detail-label';
        label.textContent=typeof friendly==='object'&&(friendly[key])||key.replaceAll('_',' ');
        const input=document.createElement('textarea');
        input.dataset.detailKey=key;
        input.maxLength=10000;
        input.rows=2;
        input.value=order.details?.[key]||'';
        label.append(input);
        dynamic.append(label);
      }
    }
    dialog.showModal();
    form.elements.title.focus();
  }
  dialog.querySelector('#edit-close').onclick=()=>dialog.close();
  dialog.querySelector('#edit-cancel').onclick=()=>dialog.close();
  dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
  document.addEventListener('click',event=>{
    const btn=event.target.closest('[data-edit-order]');
    if(!btn)return;
    event.preventDefault();event.stopPropagation();
    open(Number(btn.dataset.editOrder));
  },true);
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!current)return;
    const details={};
    dynamic.querySelectorAll('[data-detail-key]').forEach(input=>{details[input.dataset.detailKey]=input.value});
    submit.disabled=true;error.textContent='';
    try{
      const updated=await api('/api/work-orders/'+current.id,{method:'PATCH',body:{
        title:form.elements.title.value.trim(),
        priority:form.elements.priority.value,
        notes:form.elements.notes.value,
        details
      }});
      dialog.close();
      await showOrder(updated.id);
      toast('Work order updated. Drawing and document revisions unchanged.');
    }catch(e){error.textContent=e.message||'Unable to save changes'}
    finally{submit.disabled=false}
  });
})();