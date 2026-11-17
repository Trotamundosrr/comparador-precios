async function iniciarPanel() {
    const contenedor = document.getElementById("productos-tienda");
    const formulario = document.getElementById("form-producto");
    const agregar = document.getElementById("agregar-producto");
    const aviso = document.getElementById("mensaje-producto");
    const salir = document.getElementById("cerrar-sesion");
    const token = localStorage.getItem("token_comercio");

    function volverAlAcceso() {
        localStorage.removeItem("token_comercio");
        localStorage.removeItem("tienda_comercio");
        window.location.replace("/acceso/");
    }

    if (!token) {
        volverAlAcceso();
        return;
    }

    // Todas las solicitudes privadas usan el token del comercio.
    async function solicitar(url, metodo = "GET", cuerpo = null) {
        const opciones = {
            method: metodo,
            headers: {
                Authorization: "Token " + token,
                Accept: "application/json"
            }
        };

        if (cuerpo !== null) {
            opciones.headers["Content-Type"] = "application/json";
            opciones.body = JSON.stringify(cuerpo);
        }

        const respuesta = await fetch(url, opciones);

        if (respuesta.status === 401) {
            volverAlAcceso();
            throw new Error("La sesión ya no es válida.");
        }

        if (respuesta.status === 204) {
            return null;
        }

        const datos = await respuesta.json().catch(() => null);

        if (!respuesta.ok) {
            const detalle = datos
                ? JSON.stringify(datos)
                : "Error HTTP " + respuesta.status;

            throw new Error(detalle);
        }

        return datos;
    }

    function crearBoton(texto, estilo) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "btn btn-sm " + estilo;
        boton.textContent = texto;
        return boton;
    }

    function crearFila(producto) {
        const fila = document.createElement("li");
        fila.className = "list-group-item p-3";

        const nombre = document.createElement("strong");
        nombre.textContent = [
            producto.nombre,
            producto.marca,
            producto.presentacion
        ].filter(Boolean).join(" · ");

        const edicion = document.createElement("form");
        edicion.className = "d-flex flex-wrap gap-2 align-items-center mt-2";

        const etiqueta = document.createElement("label");
        etiqueta.htmlFor = "precio-" + producto.id;
        etiqueta.textContent = "Precio (Bs)";

        const campo = document.createElement("input");
        campo.id = etiqueta.htmlFor;
        campo.type = "number";
        campo.min = "0.01";
        campo.max = "99999999.99";
        campo.step = "0.01";
        campo.required = true;
        campo.value = producto.precio;
        campo.className = "form-control form-control-sm w-auto";

        const guardar = crearBoton("Guardar", "btn-outline-success");
        guardar.type = "submit";

        const retirar = crearBoton("Retirar producto", "btn-outline-danger");
        const confirmar = crearBoton("Confirmar retiro", "btn-danger");
        const cancelar = crearBoton("Cancelar", "btn-outline-secondary");

        confirmar.hidden = true;
        cancelar.hidden = true;

        const mensaje = document.createElement("p");
        mensaje.className = "small mt-2 mb-0";
        mensaje.setAttribute("role", "status");

        function ocupado(valor) {
            campo.disabled = valor;
            guardar.disabled = valor;
            retirar.disabled = valor;
            confirmar.disabled = valor;
            cancelar.disabled = valor;
        }

        edicion.addEventListener("submit", async (evento) => {
            evento.preventDefault();

            ocupado(true);
            mensaje.textContent = "Guardando precio...";

            try {
                const actualizado = await solicitar(
                    "/api/mi-tienda/productos/" + producto.id + "/",
                    "PATCH",
                    { precio: campo.value }
                );

                campo.value = actualizado.precio;
                mensaje.textContent = "Precio guardado.";
            } catch (error) {
                mensaje.textContent = error.message;
            } finally {
                ocupado(false);
            }
        });

        retirar.addEventListener("click", () => {
            retirar.hidden = true;
            confirmar.hidden = false;
            cancelar.hidden = false;
            guardar.disabled = true;
            campo.disabled = true;
            mensaje.textContent = "¿Retirar este producto de tu tienda?";
        });

        cancelar.addEventListener("click", () => {
            retirar.hidden = false;
            confirmar.hidden = true;
            cancelar.hidden = true;
            guardar.disabled = false;
            campo.disabled = false;
            mensaje.textContent = "";
        });

        confirmar.addEventListener("click", async () => {
            ocupado(true);
            mensaje.textContent = "Retirando producto...";

            try {
                await solicitar(
                    "/api/mi-tienda/productos/" + producto.id + "/",
                    "DELETE"
                );

                fila.remove();

                if (!contenedor.querySelector("li")) {
                    contenedor.textContent = "Tu tienda aún no tiene productos.";
                }
            } catch (error) {
                mensaje.textContent = error.message;
                ocupado(false);
            }
        });

        edicion.append(
            etiqueta,
            campo,
            guardar,
            retirar,
            confirmar,
            cancelar
        );

        fila.append(nombre, edicion, mensaje);
        return fila;
    }

    async function cargarProductos() {
        contenedor.textContent = "Cargando productos...";

        try {
            const productos = [];
            let url = "/api/mi-tienda/productos/";

            // Leer también las siguientes páginas de resultados.
            while (url) {
                const datos = await solicitar(url);

                if (Array.isArray(datos)) {
                    productos.push(...datos);
                    url = null;
                } else {
                    productos.push(...datos.results);
                    url = datos.next;
                }
            }

            if (productos.length === 0) {
                contenedor.textContent = "Tu tienda aún no tiene productos.";
                return;
            }

            const lista = document.createElement("ul");
            lista.className = "list-group";

            for (const producto of productos) {
                lista.appendChild(crearFila(producto));
            }

            contenedor.replaceChildren(lista);
        } catch (error) {
            contenedor.textContent = error.message;
        }
    }

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const nombre = document.getElementById("producto-nombre").value.trim();
        const marca = document.getElementById("producto-marca").value.trim();
        const presentacion = document.getElementById("producto-presentacion").value.trim();
        const precio = document.getElementById("producto-precio").value;

        if (!nombre || !presentacion) {
            aviso.textContent = "Completá el nombre y la presentación.";
            aviso.className = "text-danger mt-3";
            return;
        }

        agregar.disabled = true;
        agregar.textContent = "Guardando...";
        aviso.textContent = "";

        try {
            await solicitar("/api/mi-tienda/productos/", "POST", {
                nombre,
                marca,
                presentacion,
                precio,
                disponible: true
            });

            formulario.reset();
            aviso.textContent = "Producto publicado correctamente.";
            aviso.className = "text-success mt-3";

            await cargarProductos();
        } catch (error) {
            aviso.textContent = error.message;
            aviso.className = "text-danger mt-3";
        } finally {
            agregar.disabled = false;
            agregar.textContent = "Agregar producto";
        }
    });

    salir.addEventListener("click", async () => {
        salir.disabled = true;

        try {
            await solicitar("/api/auth/logout/", "POST");
            volverAlAcceso();
        } catch (error) {
            aviso.textContent = error.message;
            aviso.className = "text-danger mt-3";
            salir.disabled = false;
        }
    });

    try {
        const tienda = await solicitar("/api/mi-tienda/");
        document.getElementById("nombre-tienda").textContent = tienda.nombre;
        agregar.disabled = false;
        await cargarProductos();
    } catch (error) {
        contenedor.textContent = error.message;
    }
}

iniciarPanel();