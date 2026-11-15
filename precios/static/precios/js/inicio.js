document.addEventListener("DOMContentLoaded", function () {
    cargarPaginaInicial();

    document
        .getElementById("form-busqueda")
        .addEventListener("submit", function (evento) {
            evento.preventDefault();
            buscarProductos();
        });

    document
        .getElementById("orden-resultados")
        .addEventListener("change", function () {
            const texto = document
                .getElementById("texto-busqueda")
                .value
                .trim();

            const categoria = document
                .getElementById("categoria-busqueda")
                .value;

            if (texto || categoria) {
                buscarProductos();
            }
        });
});


function escaparHtml(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatearPrecio(valor) {
    const numero = Number(valor);

    if (Number.isNaN(numero)) {
        return "0,00";
    }

    return numero.toLocaleString("es-BO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}


function formatearFecha(valor) {
    if (!valor) {
        return "Sin fecha";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return valor;
    }

    return fecha.toLocaleDateString("es-BO");
}


function obtenerLista(datos) {
    if (Array.isArray(datos)) {
        return datos;
    }

    return datos.results || [];
}


function crearImagen(url, textoAlternativo, claseCss) {
    if (!url) {
        return `
            <div class="bg-light text-secondary d-flex align-items-center
                        justify-content-center ${claseCss}">
                Sin imagen
            </div>
        `;
    }

    return `
        <img
            src="${escaparHtml(url)}"
            alt="${escaparHtml(textoAlternativo)}"
            class="${claseCss}"
        >
    `;
}


async function solicitarJson(url) {
    const respuesta = await fetch(url);

    if (!respuesta.ok) {
        throw new Error(`Error HTTP ${respuesta.status}`);
    }

    return respuesta.json();
}


async function cargarPaginaInicial() {
    try {
        const [inicio, tiendas] = await Promise.all([
            solicitarJson("/api/inicio/"),
            solicitarJson("/api/tiendas/")
        ]);

        mostrarCategorias(inicio.categorias || []);
        mostrarPromociones(inicio.promociones_destacadas || []);
        mostrarTiendas(obtenerLista(tiendas));

    } catch (error) {
        console.error(error);

        document.getElementById("lista-ofertas").innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    No se pudieron cargar las promociones.
                </div>
            </div>
        `;

        document.getElementById("lista-tiendas").innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    No se pudieron cargar los comercios.
                </div>
            </div>
        `;
    }
}


function mostrarCategorias(categorias) {
    const selector = document.getElementById("categoria-busqueda");

    categorias.forEach(function (categoria) {
        const opcion = document.createElement("option");
        opcion.value = categoria.slug;
        opcion.textContent = categoria.nombre;
        selector.appendChild(opcion);
    });
}


function mostrarPromociones(promociones) {
    const contenedor = document.getElementById("lista-ofertas");

    if (promociones.length === 0) {
        contenedor.innerHTML = `
            <div class="col-12">
                <div class="estado-vacio">
                    No existen promociones activas en este momento.
                </div>
            </div>
        `;
        return;
    }

    contenedor.innerHTML = promociones.map(function (promocion) {
        const nombreProducto = promocion.producto
            ? promocion.producto.nombre
            : "Promoción general";

        return `
            <div class="col-md-6 col-lg-4">
                <article class="card card-promocion shadow-sm position-relative">
                    <span class="badge bg-danger etiqueta-oferta">
                        Oferta
                    </span>

                    ${crearImagen(
                        promocion.imagen,
                        promocion.titulo,
                        "card-img-top imagen-promocion"
                    )}

                    <div class="card-body">
                        <p class="text-success fw-semibold mb-1">
                            ${escaparHtml(promocion.tienda.nombre)}
                        </p>

                        <h3 class="h5 fw-bold">
                            ${escaparHtml(promocion.titulo)}
                        </h3>

                        <p class="text-secondary mb-2">
                            ${escaparHtml(nombreProducto)}
                        </p>

                        <p class="precio-destacado mb-2">
                            ${
                                promocion.precio_promo
                                    ? `Bs ${formatearPrecio(promocion.precio_promo)}`
                                    : "Consultar promoción"
                            }
                        </p>

                        <small class="text-secondary">
                            Válida hasta:
                            ${formatearFecha(promocion.valida_hasta)}
                        </small>
                    </div>
                </article>
            </div>
        `;
    }).join("");
}


function mostrarTiendas(tiendas) {
    const contenedor = document.getElementById("lista-tiendas");

    if (tiendas.length === 0) {
        contenedor.innerHTML = `
            <div class="col-12">
                <div class="estado-vacio">
                    Todavía no existen comercios registrados.
                </div>
            </div>
        `;
        return;
    }

    contenedor.innerHTML = tiendas.map(function (tienda) {
        return `
            <div class="col-md-6 col-lg-4">
                <article class="card card-tienda shadow-sm">
                    <div class="card-body">
                        <div class="d-flex align-items-center gap-3 mb-3">
                            ${crearImagen(
                                tienda.logo,
                                tienda.nombre,
                                "logo-tienda"
                            )}

                            <div>
                                <h3 class="h5 fw-bold mb-1">
                                    ${escaparHtml(tienda.nombre)}
                                </h3>

                                <span class="badge bg-success-subtle text-success">
                                    ${escaparHtml(tienda.zona || "Cochabamba")}
                                </span>
                            </div>
                        </div>

                        <p class="text-secondary mb-2">
                            ${escaparHtml(
                                tienda.direccion || "Dirección no registrada"
                            )}
                        </p>

                        <p class="mb-0 fw-semibold">
                            ${tienda.cantidad_productos} productos publicados
                        </p>
                    </div>
                </article>
            </div>
        `;
    }).join("");
}


async function buscarProductos() {
    const texto = document
        .getElementById("texto-busqueda")
        .value
        .trim();

    const categoria = document
        .getElementById("categoria-busqueda")
        .value;

    let orden = document
        .getElementById("orden-resultados")
        .value;

    const mensaje = document.getElementById("mensaje-busqueda");
    const cargando = document.getElementById("cargando-resultados");
    const contenedor = document.getElementById("resultados-comparador");

    if (!texto && !categoria) {
        mensaje.classList.remove("d-none");
        mensaje.className = "alert alert-warning";
        mensaje.textContent =
            "Escribe un producto o selecciona una categoría.";
        return;
    }

    if (!texto && orden === "relevancia") {
        orden = "precio";
    }

    const parametros = new URLSearchParams();

    if (texto) {
        parametros.set("q", texto);
    }

    if (categoria) {
        parametros.set("categoria", categoria);
    }

    parametros.set("orden", orden);

    mensaje.classList.add("d-none");
    contenedor.innerHTML = "";
    cargando.classList.remove("d-none");

    try {
        const datos = await solicitarJson(
            `/api/comparador/?${parametros.toString()}`
        );

        mostrarResultados(obtenerLista(datos));

    } catch (error) {
        console.error(error);

        contenedor.innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    Ocurrió un error al buscar los productos.
                </div>
            </div>
        `;

    } finally {
        cargando.classList.add("d-none");
    }
}


function mostrarResultados(resultados) {
    const contenedor = document.getElementById("resultados-comparador");

    if (resultados.length === 0) {
        contenedor.innerHTML = `
            <div class="col-12">
                <div class="estado-vacio">
                    No encontramos productos que coincidan con la búsqueda.
                </div>
            </div>
        `;
        return;
    }

    contenedor.innerHTML = resultados.map(function (resultado) {
        const producto = resultado.producto;

        const precios = resultado.precios.map(function (registro) {
            const tienePromocion =
                registro.promocion &&
                Number(registro.precio_efectivo) < Number(registro.precio);

            return `
                <div class="border rounded-3 p-3 mb-2
                            ${registro.es_mas_barato
                                ? "border-success bg-success-subtle"
                                : "bg-white"}">

                    <div class="d-flex flex-column flex-md-row
                                justify-content-between gap-2">

                        <div>
                            <p class="fw-bold mb-1">
                                ${escaparHtml(registro.tienda.nombre)}
                            </p>

                            <small class="fecha-actualizacion">
                                Actualizado:
                                ${formatearFecha(registro.actualizado)}
                            </small>
                        </div>

                        <div class="text-md-end">
                            ${
                                tienePromocion
                                    ? `
                                        <small class="text-decoration-line-through
                                                      text-secondary d-block">
                                            Bs ${formatearPrecio(registro.precio)}
                                        </small>
                                    `
                                    : ""
                            }

                            <span class="fs-5 fw-bold text-success">
                                Bs ${formatearPrecio(registro.precio_efectivo)}
                            </span>

                            ${
                                registro.es_mas_barato
                                    ? `
                                        <span class="badge bg-success ms-2">
                                            Mejor precio
                                        </span>
                                    `
                                    : ""
                            }
                        </div>
                    </div>

                    ${
                        registro.promocion
                            ? `
                                <div class="mt-2">
                                    <span class="badge bg-danger">
                                        ${escaparHtml(
                                            registro.promocion.titulo
                                        )}
                                    </span>
                                </div>
                            `
                            : ""
                    }
                </div>
            `;
        }).join("");

        return `
            <div class="col-12">
                <article class="card card-producto shadow-sm">
                    <div class="card-body">
                        <div class="row g-4">
                            <div class="col-md-3">
                                ${crearImagen(
                                    producto.imagen,
                                    producto.nombre,
                                    "w-100 rounded-3 imagen-producto"
                                )}
                            </div>

                            <div class="col-md-9">
                                <div class="d-flex flex-column flex-md-row
                                            justify-content-between gap-3 mb-3">
                                    <div>
                                        <span class="badge bg-secondary mb-2">
                                            ${
                                                escaparHtml(
                                                    producto.categoria
                                                    || "Sin categoría"
                                                )
                                            }
                                        </span>

                                        <h3 class="h4 fw-bold mb-1">
                                            ${escaparHtml(producto.nombre)}
                                        </h3>

                                        <p class="text-secondary mb-0">
                                            ${escaparHtml(producto.marca || "")}
                                            ${escaparHtml(
                                                producto.presentacion || ""
                                            )}
                                        </p>
                                    </div>

                                    <div class="text-md-end">
                                        <small class="text-secondary d-block">
                                            Desde
                                        </small>

                                        <span class="precio-destacado">
                                            Bs ${formatearPrecio(
                                                resultado.precio_minimo
                                            )}
                                        </span>
                                    </div>
                                </div>

                                ${precios}
                            </div>
                        </div>
                    </div>
                </article>
            </div>
        `;
    }).join("");

    document
        .getElementById("comparador")
        .scrollIntoView({ behavior: "smooth" });
}