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
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const content = document.querySelector('.paper-content');
    content.getAnimations().forEach(animation => animation.cancel());
    content.animate([{opacity:.25,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}], {duration:420,easing:'cubic-bezier(.22,1,.36,1)'});
  }
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
  if (updateUrl && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.querySelector(`#panel-${kind}`).animate([{opacity:.3,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}], {duration:400,easing:'cubic-bezier(.22,1,.36,1)'});
  }
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

const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
if ('IntersectionObserver' in window && !motionPreference.matches) {
  document.documentElement.classList.add('motion-ready');
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    }
  }, {threshold:.08, rootMargin:'0px 0px 30px 0px'});
  document.querySelectorAll('[data-reveal]').forEach(element => observer.observe(element));
}

const menu = document.querySelector('#menu-dialog');
const menuToggle = document.querySelector('#menu-toggle');
let menuClosing = false;

function closeMenu(immediate = false) {
  if (!menu.open || menuClosing) return;
  menuClosing = true;
  menu.classList.remove('is-open');
  menuToggle.setAttribute('aria-expanded','false');
  setTimeout(() => {
    menu.close();
    document.body.classList.remove('menu-open');
    menuClosing = false;
    if (menuToggle.getClientRects().length) menuToggle.focus({preventScroll:true});
  }, immediate || motionPreference.matches ? 0 : 400);
}

menuToggle.addEventListener('click', () => {
  if (menu.open) return closeMenu();
  menu.showModal();
  document.body.classList.add('menu-open');
  menuToggle.setAttribute('aria-expanded','true');
  requestAnimationFrame(() => menu.classList.add('is-open'));
});
menu.querySelector('.menu-close').addEventListener('click', () => closeMenu());
menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => closeMenu()));
menu.addEventListener('cancel', event => { event.preventDefault(); closeMenu(); });
menu.addEventListener('click', event => { if (event.target === menu) closeMenu(); });
matchMedia('(min-width: 768px)').addEventListener('change', event => { if (event.matches) closeMenu(true); });
