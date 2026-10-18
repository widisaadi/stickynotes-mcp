'use strict';

const examples = {
  find: {title:'For the week', lines:[['Outline the new idea','done'],['Review the release checklist','highlighted'],['Make a little time to read','']], footer:'The thought you were looking for.', prompt:'Find my note about the release checklist.', caption:'A keyword search brings the right note back into view.', icon:'i-search'},
  write: {title:'One more thing', lines:[['Outline the new idea','done'],['Review the release checklist',''],['Send the draft to the team','highlighted']], footer:'A next step, added to the list.', prompt:'Add “Send the draft to the team” to my note.', caption:'Append a new task while keeping the rest of your note.', icon:'i-edit'},
  export: {title:'Notes to take along', lines:[['For the week',''],['Ideas for a rainy day',''],['The reading list','highlighted']], footer:'Ready for a Markdown or JSON export.', prompt:'Export my active sticky notes as Markdown.', caption:'Your active notes, collected in a file you can use elsewhere.', icon:'i-export'}
};

function setQuery(key, value) {
  const url = new URL(location.href);
  url.searchParams.set(key,value);
  history.replaceState(null,'',url);
}

function showExample(kind, updateUrl = true) {
  if (!Object.hasOwn(examples,kind)) kind='find';
  const item=examples[kind];
  document.querySelector('#note-title').textContent=item.title;
  const lines=document.querySelector('#note-lines');
  lines.replaceChildren(...item.lines.map(([label,className]) => {
    const li=document.createElement('li');
    li.textContent=label;
    li.className=className;
    return li;
  }));
  document.querySelector('#note-footer').textContent=item.footer;
  document.querySelector('#demo-paper').dataset.kind=kind;
  document.querySelector('#sample-prompt').textContent=item.prompt;
  document.querySelector('.sample-request use').setAttribute('href',`#${item.icon}`);
  document.querySelector('#example-caption').textContent=item.caption;
  document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.example===kind)));
  if(updateUrl) setQuery('example',kind);
}

function showSetup(kind, updateUrl = true, focus = false) {
  if(!['install','config'].includes(kind)) kind='install';
  document.querySelectorAll('[data-setup]').forEach(button => {
    const selected=button.dataset.setup===kind;
    button.setAttribute('aria-selected',String(selected));
    button.tabIndex=selected ? 0 : -1;
    document.querySelector(`#panel-${button.dataset.setup}`).hidden=!selected;
    if(selected && focus) button.focus();
  });
  if(updateUrl) setQuery('setup',kind);
}

document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click',()=>showExample(button.dataset.example)));
document.querySelectorAll('[data-setup]').forEach(button => {
  button.addEventListener('click',()=>showSetup(button.dataset.setup));
  button.addEventListener('keydown',event=>{
    const keys=['ArrowLeft','ArrowRight','Home','End'];
    if(!keys.includes(event.key)) return;
    event.preventDefault();
    const next=event.key==='Home' ? 'install' : event.key==='End' ? 'config' : button.dataset.setup==='install' ? 'config' : 'install';
    showSetup(next,true,true);
  });
});

document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click',async()=>{
  const code=document.getElementById(button.dataset.copy);
  const status=document.querySelector('#copy-status');
  const label=button.querySelector('span');
  const original=button.dataset.copy==='install-code' ? 'Copy commands' : 'Copy config';
  try {
    if(!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(code.textContent);
    label.textContent='Copied';
    status.textContent=button.dataset.copy==='install-code' ? 'Installation commands copied.' : 'Configuration copied. Replace the example paths before saving.';
    clearTimeout(button.copyTimer);
    button.copyTimer=setTimeout(()=>label.textContent=original,2500);
  } catch {
    const range=document.createRange();
    range.selectNodeContents(code);
    const selection=window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent='Copy access is unavailable. The code is selected; copy it manually.';
  }
}));

function restoreFromUrl() {
  const params=new URLSearchParams(location.search);
  showExample(params.get('example') || 'find',false);
  showSetup(params.get('setup') || 'install',false);
}
restoreFromUrl();
addEventListener('popstate',restoreFromUrl);
