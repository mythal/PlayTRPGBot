let reply_list = document.querySelectorAll('.reply a');

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