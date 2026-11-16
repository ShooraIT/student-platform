(function () {
  var body = document.getElementById("merch-admin-catalog");
  if (!body) return;
  var base = document.currentScript && document.currentScript.dataset.base || "";
  fetch(base + "/static/shop/merch/catalog.json").then(function (response) { if (!response.ok) throw new Error("catalog"); return response.json(); }).then(function (data) {
    body.innerHTML = "";
    (data.items || []).forEach(function (item) {
      var row = document.createElement("tr");
      var fields = [item.title, item.category === "clothing" ? "Одежда" : "Аксессуары", "Не задана", "Не задан", item.sale_status === "award_only" ? "Только награда" : (item.asset_status === "missing" ? "Черновик · нужен макет" : "Черновик · макет")];
      fields.forEach(function (value) { var cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell); });
      var action = document.createElement("td"); var button = document.createElement("button"); button.className = "btn secondary small"; button.type = "button"; button.textContent = "Настроить";
      button.dataset.shopEdit = ""; button.dataset.productName = item.title; button.dataset.productKind = item.type === "reward" ? "reward" : "merch"; button.dataset.productCategory = item.category; button.dataset.productPrice = "0"; button.dataset.productStock = "0"; action.appendChild(button); row.appendChild(action); body.appendChild(row);
    });
  }).catch(function () { body.innerHTML = '<tr><td colspan="6">Каталог недоступен</td></tr>'; });
}());
