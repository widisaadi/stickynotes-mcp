'use strict';

// The shared engine is unmodified. Only the illustrative note responds here.
const scrollDesktop=matchMedia('(min-width: 768px)');
const scrollReduced=matchMedia('(prefers-reduced-motion: reduce)');
let scrollInstance;
function syncScrollCraft() {
  scrollInstance?.destroy();
  scrollInstance=null;
  document.querySelectorAll('[data-sc-parallax], [data-sc-reveal]').forEach(el=>{
    el.style.removeProperty('transform');el.style.removeProperty('clip-path');
  });
  if (scrollDesktop.matches && !scrollReduced.matches && !document.documentElement.classList.contains('keyboard-input')) {
    scrollInstance=window.ScrollCraft?.mount(document.querySelector('main'));
  }
}
syncScrollCraft();
scrollDesktop.addEventListener('change',syncScrollCraft);
scrollReduced.addEventListener('change',syncScrollCraft);
document.addEventListener('keydown',()=>{if(scrollInstance)syncScrollCraft();});
document.addEventListener('pointerdown',()=>{if(!scrollInstance)syncScrollCraft();});

const trail=document.querySelector('.paper-trail');
if (document.body.dataset.version==='cinematic') {
  const demo=document.querySelector('#examples');
  const controls=demo.querySelector('.example-controls');
  const toggle=document.createElement('button');
  toggle.type='button';
  toggle.className='demo-playback';
  let paused=scrollReduced.matches;
  let visible=false;
  let timer;
  function scheduleDemo() {
    clearTimeout(timer);
    toggle.textContent=paused?'Play examples':'Pause examples';
    toggle.setAttribute('aria-pressed',String(!paused));
    const focused=controls.contains(document.activeElement);
    demo.querySelector('#example-caption').setAttribute('aria-live',paused||focused?'polite':'off');
    if(paused||!visible||document.hidden||focused) return;
    timer=setTimeout(()=>{
      const order=['find','write','export'];
      const current=demo.querySelector('[data-example][aria-pressed=true]').dataset.example;
      showExample(order[(order.indexOf(current)+1)%order.length],false,true);
      scheduleDemo();
    },3000);
  }
  toggle.addEventListener('click',()=>{paused=!paused;scheduleDemo();});
  demo.querySelector('.demo-toolbar').append(toggle);
  controls.addEventListener('focusin',scheduleDemo);
  controls.addEventListener('focusout',()=>requestAnimationFrame(scheduleDemo));
  controls.addEventListener('click',scheduleDemo);
  document.addEventListener('visibilitychange',scheduleDemo);
  scrollReduced.addEventListener('change',()=>{if(scrollReduced.matches)paused=true;scheduleDemo();});
  new IntersectionObserver(entries=>{
    visible=entries[0].isIntersecting;scheduleDemo();
  },{threshold:.3}).observe(demo);
  scheduleDemo();
}
if (trail) {
  const states={
    find:['For the week','Review the release checklist.\nMake a little time to read.','A thought, found.','Find my release checklist.'],
    write:['One more thing','Review the release checklist.\n✓ Send the draft to the team.','A next step, added.','Add “Send the draft to the team.”'],
    export:['Notes to take along','For the week.md\nIdeas for a rainy day.md','Ready to carry forward.','Export my notes as Markdown.']
  };
  let current='find';
  const observer=new IntersectionObserver(entries=>{
    if(!scrollDesktop.matches||scrollReduced.matches) return;
    for(const entry of entries) {
      if(!entry.isIntersecting||entry.target.dataset.trail===current) continue;
      current=entry.target.dataset.trail;
      const [title,body,stamp,request]=states[current];
      document.querySelector('#trail-note-title').textContent=title;
      document.querySelector('#trail-note-body').textContent=body;
      document.querySelector('#trail-note-stamp').textContent=stamp;
      document.querySelector('#trail-request').textContent=request;
      const note=document.querySelector('.trail-note');
      note.getAnimations().forEach(a=>a.cancel());
      if(!document.documentElement.classList.contains('keyboard-input')) note.animate([{opacity:.6,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'cubic-bezier(.22,1,.36,1)'});
    }
  },{rootMargin:'-30% 0px -35% 0px',threshold:0});
  document.querySelectorAll('[data-trail]').forEach(el=>observer.observe(el));
}
