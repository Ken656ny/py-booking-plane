       async function cargarVuelos() {
            const container = document.getElementById('vuelos-container');
            container.innerHTML = 'Cargando vuelos...';

            try {
                const res = await fetch('http://127.0.0.1:5000/vuelos'); // Ajusta tu URL si cambia
                const data = await res.json();

                if (!data.vuelos || data.vuelos.length === 0) {
                    container.innerHTML = '<p>No hay vuelos disponibles</p>';
                    return;
                }

                container.innerHTML = ''; // limpiar mientras se agregan vuelos
                
                data.vuelos.forEach((vuelo, index) => {
                    const vueloHTML = `
<div class="bg-gray-50 border border-gray-200 rounded-2xl p-4 flex flex-col gap-3 hover:shadow-md transition text-black">
  <div class="flex items-center gap-2 text-sm text-gray-600"><span class="text-indigo-600 font-bold">✈</span> Vuelo #${index + 1}</div>
  <div class="flex justify-between items-center gap-2">
    <div>
      <p class="text-sm font-medium text-gray-800">Origen</p>
      <p class="text-gray-600">${vuelo.origen}</p>
    </div>
    <div>
      <p class="text-sm font-medium text-gray-800">Destino</p>
      <p class="text-gray-600">${vuelo.destino}</p>
    </div>
  </div>
  <div class="flex justify-between items-center gap-2">
    <div>
      <p class="text-sm font-medium text-gray-800">Fecha</p>
      <p class="text-gray-600">${vuelo.fecha}</p>
    </div>
    <div>
      <p class="text-sm font-medium text-gray-800">Precio</p>
      <p class="text-gray-600">$${vuelo.precio.toLocaleString()}</p>
    </div>
  </div>
  <div class="flex justify-between items-center gap-2">
    <div>
      <p class="text-sm font-medium text-gray-800">Total de asientos</p>
      <p class="text-gray-600">${vuelo.total_asientos}</p>
    </div>
    <div>
      <p class="text-sm font-medium text-gray-800">Ocupados </p>
      <p class="text-gray-600">${vuelo.asientos_ocupados} </p>
    </div>
  </div>
  <button class="mt-2 w-full rounded-xl bg-indigo-600 text-white py-2 hover:bg-indigo-700 transition"
          onclick="reservarVuelo(${vuelo.id_vuelo})">Reservar</button>
</div>
          `;
                    container.innerHTML += vueloHTML;
                });

            } catch (err) {
                console.error(err);
                container.innerHTML = '<p>Error cargando vuelos</p>';
            }
        }

        function reservarVuelo(idVuelo) {
            localStorage.setItem("id_vuelo",idVuelo)
            window.location.href="elegir_silla.html"
        }

const vueloId = localStorage.getItem("id_vuelo"); // leer el vuelo seleccionado

async function cargarAsientos() {
    try {
        const res = await fetch(`http://127.0.0.1:5000/vuelo/${vueloId}/asientos`);
        const data = await res.json();
        const contenedor = document.getElementById("asientosContainer");

        contenedor.innerHTML = ""; // limpiar antes de cargar

        data.asientos.forEach(a => {
            const btn = document.createElement("button");
            btn.className = "seat";
            btn.dataset.state = a.estado === "DISPONIBLE" ? "empty" : (a.estado === "RESERVADO" ? "occupied" : "blocked");
            btn.textContent = a.estado === "RESERVADO" ? "✖" : "";
            btn.addEventListener("click", () => seleccionarAsiento(btn, a.nombre_asiento));
            contenedor.appendChild(btn);
        });
    } catch (err) {
        console.error(err);
    }
}

// lógica de selección de asientos
const MAX = 5;
let seleccionados = [];
function seleccionarAsiento(btn, nombre) {
    if(btn.dataset.state === "occupied" || btn.dataset.state === "blocked") return;
    if(btn.dataset.state === "selected") {
        btn.dataset.state = "empty";
        btn.textContent = "";
        seleccionados = seleccionados.filter(x => x !== nombre);
        actualizarContador();
        return;
    }
    if(seleccionados.length >= MAX) return alert(`Máximo ${MAX} asientos`);
    btn.dataset.state = "selected";
    btn.textContent = "👤";
    seleccionados.push(nombre);
    actualizarContador();
}

function actualizarContador() {
    document.getElementById("counter").innerHTML = `máximo <b>${MAX}</b> personas — seleccionados: <b>${seleccionados.length}</b>`;
}

window.onload = cargarAsientos;