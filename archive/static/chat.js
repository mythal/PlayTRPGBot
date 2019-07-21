let reply_list = document.querySelectorAll('.reply-to-link');

function highlight() {
    let link = document.querySelector(this.getAttribute('href'));
    link.className = link.className.replace(' highlight', '');
    setTimeout(() => {
        link.className += ' highlight';
    }, 200);
}

for (let i = 0; i < reply_list.length; i++) {
    reply_list[i].addEventListener('click', highlight);
}

const stringHash = s => {
  let hash = 0;
  let i;
  let chr;
  if (s.length === 0) return hash;
  for (i = 0; i < s.length; i++) {
    chr = s.charCodeAt(i);
    // tslint:disable-next-line:no-bitwise
    hash = ((hash << 5) - hash) + chr;
    // tslint:disable-next-line:no-bitwise
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
};

const nameToHSL = name => {
  const hash = stringHash(name);
  const h = hash % 365;
  const s = hash % 100;
  const l = 35;
  return `hsl(${ h }, ${ s }%, ${ l }%)`;
};

let log_list = document.querySelectorAll('.log');

for (let i = 0; i < log_list.length; i++) {
    const log = log_list[i];
    const speaker = log.querySelector(".speaker");
    if (speaker) {
        log.style.color = nameToHSL(speaker.innerHTML);
    }
}

