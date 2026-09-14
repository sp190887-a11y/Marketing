/* test QR panel */
const ampProfileWithQr=profile;
profile=function(){const qr=`https://quickchart.io/qr?size=220&margin=1&text=${encodeURIComponent(location.origin+location.pathname+'?testlogin=1')}`;return ampProfileWithQr().replace(/<button class="rowcard card" data-action="test-login">[\s\S]*?<\/button>/,`<section class="login-card card"><img class="login-qr" src="${qr}" alt="QR для тестового входа"><div><h3>QR-код для входа</h3><p>Тестовая проверка вместо SMS. На тесте используем единый код <b>1111</b>; позже заменяем его настоящей отправкой через Python API.</p><span class="test-code">1111</span></div></section>`)};
render();
