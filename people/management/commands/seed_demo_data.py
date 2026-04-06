from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError

from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.models import EvaluationCycle
from people.models import Department, Employee, Role


COMPETENCY_DATA = {
    "Customer Centric": {
        "Básico": [
            "Atiende a los clientes con cortesía y respeto en todas las interacciones",
            "Escucha activamente las necesidades expresadas por el cliente antes de ofrecer una solución",
            "Cumple los tiempos de respuesta establecidos para solicitudes o reclamos",
        ],
        "Avanzado": [
            "Personaliza la atención según el perfil y preferencias del cliente",
            "Anticipa necesidades basándose en interacciones previas o historial de compra",
            "Gestiona objeciones o quejas de forma eficiente y con satisfacción del cliente",
        ],
        "Experto": [
            "Diseña mejoras en procesos de atención basadas en feedback del cliente",
            "Define y documenta estándares de experiencia de cliente que son utilizados por su área o por otros equipos",
            "Implementa iniciativas que elevan los indicadores de fidelización",
        ],
    },
    "Orientación Omnicanal": {
        "Básico": [
            "Atiende solicitudes provenientes de cualquier canal siguiendo los mismos estándares de calidad y tiempos de respuesta",
            "Mantiene coherencia en la información entregada por cualquier canal",
            "Deriva las solicitudes al canal o área correspondiente sin tener preferencias de canal y atendiendo solo a necesidades de empresa",
        ],
        "Avanzado": [
            "Da respuesta adecuada a las necesidades de los diferentes canales teniendo en cuenta su idiosincrasia.",
            "Coordina con otras áreas o canales para resolver incidencias del cliente dentro del plazo establecido",
            "Ajusta su forma de atención según las características del canal manteniendo una experiencia consistente",
        ],
        "Experto": [
            "Define protocolos de atención que integran todos los canales de servicio y venta",
            "Identifica brechas de servicio entre canales y propone mejoras para estandarizar la experiencia del cliente",
            "Lidera iniciativas para mejorar la coordinación operativa entre canales",
        ],
    },
    "Colaboración": {
        "Básico": [
            "Comparte información relevante con su equipo",
            "Apoya a compañeros cuando se le solicita",
            "Participa activamente en reuniones de trabajo",
        ],
        "Avanzado": [
            "Coordina tareas entre áreas para cumplir objetivos comunes",
            "Resuelve conflictos de forma directa y respetuosa",
            "Fomenta la participación del equipo en decisiones operativas",
        ],
        "Experto": [
            "Construye redes de colaboración entre departamentos",
            "Lidera iniciativas transversales de mejora organizacional",
            "Desarrolla una cultura de trabajo colaborativo",
        ],
    },
    "Adaptabilidad": {
        "Básico": [
            "Acepta cambios en tareas o procesos sin resistencia",
            "Aprende nuevas herramientas cuando se le solicita",
            "Ajusta su agenda ante prioridades cambiantes",
        ],
        "Avanzado": [
            "Propone soluciones ante cambios operativos",
            "Capacita a otros en nuevos procesos",
            "Mantiene el rendimiento bajo presión o incertidumbre",
        ],
        "Experto": [
            "Lidera procesos de cambio organizacional",
            "Anticipa impactos de cambios del mercado",
            "Diseña planes de adaptación para su área",
        ],
    },
    "Orientación y Ejecución de Resultados": {
        "Básico": [
            "Cumple objetivos individuales en tiempo y forma",
            "Prioriza tareas según impacto en resultados",
            "Reporta avances periódicamente",
        ],
        "Avanzado": [
            "Optimiza recursos para mejorar resultados del área",
            "Corrige desviaciones en metas durante la ejecución",
            "Alinea su trabajo con indicadores de negocio",
        ],
        "Experto": [
            "Define metas estratégicas para su unidad",
            "Implementa sistemas de seguimiento de desempeño",
            "Logra mejoras sostenidas en rentabilidad o productividad",
        ],
    },
    "Sentido de Pertenencia": {
        "Básico": [
            "Representa la marca de forma profesional",
            "Respeta normas y valores de la empresa",
            "Participa en actividades corporativas",
        ],
        "Avanzado": [
            "Promueve activamente la cultura organizacional",
            "Defiende la reputación de la empresa ante terceros",
            "Apoya iniciativas internas de mejora",
        ],
        "Experto": [
            "Actúa como embajador de marca interna y externamente",
            "Lidera proyectos culturales",
            "Refuerza el compromiso organizacional del equipo",
        ],
    },
    "Eficiencia de Negocio": {
        "Básico": [
            "Utiliza adecuadamente los recursos asignados",
            "Reduce desperdicios en su operación diaria",
            "Sigue procedimientos establecidos",
        ],
        "Avanzado": [
            "Mejora procesos para reducir costos o tiempos",
            "Analiza indicadores operativos de su área",
            "Propone soluciones de optimización",
        ],
        "Experto": [
            "Diseña modelos de eficiencia organizacional",
            "Impacta directamente en márgenes de rentabilidad",
            "Lidera iniciativas de transformación operativa",
        ],
    },
    "Gestión y Desarrollo de Personas": {
        "Básico": [
            "Da retroalimentación básica cuando se le solicita",
            "Apoya la introducción de nuevos colaboradores",
            "Reconoce logros del equipo",
        ],
        "Avanzado": [
            "Define planes de desarrollo individuales",
            "Realiza evaluaciones de desempeño estructuradas",
            "Identifica talento dentro del equipo",
        ],
        "Experto": [
            "Diseña estrategias de desarrollo organizacional",
            "Construye planes de sucesión",
            "Forma líderes internos",
        ],
    },
    "Mentalidad Innovadora": {
        "Básico": [
            "Sugiere mejoras en su trabajo diario",
            "Prueba nuevas formas de hacer tareas",
            "Acepta ideas de otros",
        ],
        "Avanzado": [
            "Implementa mejoras operativas",
            "Participa en proyectos de innovación",
            "Evalúa riesgos y beneficios de nuevas ideas",
        ],
        "Experto": [
            "Diseña modelos de innovación organizacional",
            "Lidera lanzamientos de nuevos productos o procesos",
            "Promueve cultura de innovación continua",
        ],
    },
    "Visión de Negocio": {
        "Básico": [
            "Comprende los productos y servicios de la empresa",
            "Conoce a los principales clientes y mercados",
            "Relaciona su trabajo con los resultados del negocio",
        ],
        "Avanzado": [
            "Analiza tendencias del mercado",
            "Identifica oportunidades con impacto en negocio",
            "Apoya decisiones estratégicas del área",
        ],
        "Experto": [
            "Define estrategias de crecimiento",
            "Anticipa cambios del mercado",
            "Lidera proyectos de negocio",
        ],
    },
    "Responsabilidad": {
        "Básico": [
            "Cumple horarios y compromisos laborales",
            "Entrega tareas dentro de los plazos establecidos",
            "Sigue políticas y normas internas",
        ],
        "Avanzado": [
            "Asume errores y propone soluciones",
            "Supervisa cumplimiento de normas en su equipo",
            "Garantiza calidad en entregables",
        ],
        "Experto": [
            "Establece estándares éticos y operativos",
            "Gestiona riesgos organizacionales",
            "Responde por resultados estratégicos",
        ],
    },
}

LEVEL_MAP = {"Básico": 1, "Avanzado": 2, "Experto": 3}


class Command(BaseCommand):
    help = "Carga datos demo: empleados, jerarquía, ciclos y competencias." 

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Cargando datos demo..."))
        try:
            departments = {
                "Ventas": Department.objects.get_or_create(name="Ventas")[0],
                "Operaciones": Department.objects.get_or_create(name="Operaciones")[0],
                "People": Department.objects.get_or_create(name="People")[0],
                "Finanzas": Department.objects.get_or_create(name="Finanzas")[0],
            }
        except OperationalError as exc:
            raise CommandError(
                "No se encontraron tablas de la base de datos. Ejecuta `python manage.py migrate` antes de correr seed_demo_data."
            ) from exc

        roles = {
            "Head of Sales": Role.objects.get_or_create(name="Head of Sales", department=departments["Ventas"])[0],
            "Account Manager": Role.objects.get_or_create(name="Account Manager", department=departments["Ventas"])[0],
            "Ops Lead": Role.objects.get_or_create(name="Ops Lead", department=departments["Operaciones"])[0],
            "Ops Specialist": Role.objects.get_or_create(name="Ops Specialist", department=departments["Operaciones"])[0],
            "HRBP": Role.objects.get_or_create(name="HRBP", department=departments["People"])[0],
            "Finance Lead": Role.objects.get_or_create(name="Finance Lead", department=departments["Finanzas"])[0],
        }

        users_data = [
            ("ceo", "Ana", "García", "Head of Sales", None),
            ("ventas1", "Luis", "Pérez", "Account Manager", "ceo"),
            ("ventas2", "Marta", "Ruiz", "Account Manager", "ceo"),
            ("opslead", "Carlos", "Soto", "Ops Lead", "ceo"),
            ("ops1", "Elena", "Díaz", "Ops Specialist", "opslead"),
            ("ops2", "Jorge", "Vega", "Ops Specialist", "opslead"),
            ("hr1", "Paula", "Núñez", "HRBP", "ceo"),
            ("fin1", "Raúl", "López", "Finance Lead", "ceo"),
            ("ventas3", "Sofía", "Mena", "Account Manager", "ventas1"),
            ("ops3", "Iván", "Mora", "Ops Specialist", "opslead"),
        ]

        employees = {}
        for username, first_name, last_name, role_name, manager_username in users_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": f"{username}@demo.local",
                    "is_active": True,
                },
            )
            if not user.has_usable_password():
                user.set_password("demo12345")
                user.save()
            # Reforzamos siempre la contraseña demo para evitar usuarios con
            # password vacío/ilegible tras reinicios de BD o seeds parciales.
            user.set_password("demo12345")
            user.save(update_fields=["password"])

            role = roles[role_name]
            employee, _ = Employee.objects.get_or_create(
                user=user,
                defaults={"department": role.department, "role": role},
            )
            employee.department = role.department
            employee.role = role
            employee.save()
            employees[username] = employee

        for username, _, _, _, manager_username in users_data:
            if manager_username:
                employee = employees[username]
                employee.manager = employees[manager_username]
                employee.save(update_fields=["manager"])

        EvaluationCycle.objects.get_or_create(
            name="Ciclo 2026",
            defaults={"start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31)},
        )

        for competency_name, level_data in COMPETENCY_DATA.items():
            competency, _ = Competency.objects.get_or_create(name=competency_name)
            for level_title, behaviors in level_data.items():
                level_number = LEVEL_MAP[level_title]
                level, _ = CompetencyLevel.objects.get_or_create(
                    competency=competency,
                    level=level_number,
                    defaults={"title": level_title},
                )
                if level.title != level_title:
                    level.title = level_title
                    level.save(update_fields=["title"])

                for behavior in behaviors:
                    LevelIndicator.objects.get_or_create(level=level, text=behavior)

        all_competencies = Competency.objects.all()
        for role in Role.objects.all():
            for competency in all_competencies:
                RoleCompetencyRequirement.objects.get_or_create(
                    role=role,
                    competency=competency,
                    defaults={"required_level": 2, "weight": 1},
                )

        self.stdout.write(self.style.SUCCESS("Datos demo cargados correctamente."))
        self.stdout.write("Usuarios demo password: demo12345")
