"""Терминальное меню и обработчики действий пользователя."""

from __future__ import annotations

from typing import Any
import sqlite3
import textwrap
import getpass
import json
from .vault import Vault, VaultError

from .database import Database
from .ui import banner, clear_screen, error, info, paint, success, title


def run() -> None:
    db = None
    vault = None
    try:
        clear_screen()
        vault = unlock_vault()
        clear_screen()
        db = Database(vault.db_path, vault.schema_path)
        banner()
        if not db.fields():
            error("Поля пока не настроены. Заполните CoreDB/schema.json.")
        while True:
            print_menu()
            choice = input(paint("  [InfoCore] Выберите действие: ", "\033[91m", bold=True)).strip()
            clear_screen()
            try:
                if choice == "1":
                    create_or_extend(db)
                elif choice == "2":
                    edit_record(db)
                elif choice == "3":
                    delete_record(db)
                elif choice == "4":
                    view_data(db)
                elif choice == "5":
                    view_dossier(db)
                elif choice == "6":
                    manage_fields(db)
                elif choice == "7":
                    view_security_log(vault)
                elif choice == "0":
                    print(paint("\n  [ InfoCore offline ] До свидания!", "\033[91m", bold=True))
                    return
                else:
                    error("Неизвестный пункт меню.")
            except (ValueError, OSError, sqlite3.Error) as exc:
                db.connection.rollback()
                error(str(exc))
            if choice != "7":
                input("\nНажмите Enter для возврата в меню...")
            clear_screen()
    except (ValueError, OSError, sqlite3.Error, VaultError) as exc:
        error(str(exc))
    except (KeyboardInterrupt, EOFError):
        print("\nРабота завершена.")
    finally:
        if db is not None:
            db.close()
        if vault is not None:
            vault.close()


def unlock_vault() -> Vault:
    if Vault.exists():
        for attempt in range(1, 4):
            password = getpass.getpass("  [InfoCore] Ключ доступа: ")
            try:
                return Vault.create_or_open(password)
            except VaultError:
                error(
                    "В доступе отказано. Об инциденте будет доложено. "
                    f"Попытка {attempt}/3."
                )
        raise VaultError("Слишком много неверных попыток. Сеанс заблокирован.")
    print("\nПервый запуск защищённого хранилища.")
    password = getpass.getpass("Создайте ключ (не сохраняется отдельно): ")
    confirmation = getpass.getpass("Повторите ключ: ")
    if password != confirmation:
        raise VaultError("Ключи не совпадают.")
    return Vault.create_or_open(password)


def print_menu() -> None:
    title("ГЛАВНОЕ МЕНЮ")
    print(paint("  [1]", "\033[91m", bold=True) + " Записать данные")
    print(paint("  [2]", "\033[91m", bold=True) + " Редактировать запись")
    print(paint("  [3]", "\033[91m", bold=True) + " Удалить запись")
    print(paint("  [4]", "\033[91m", bold=True) + " Просмотреть данные")
    print(paint("  [5]", "\033[91m", bold=True) + " Открыть досье записи")
    print(paint("  [6]", "\033[91m", bold=True) + " Добавить столбец")
    print(paint("  [7]", "\033[91m", bold=True) + " Журнал безопасности")
    print(paint("  [0]", "\033[91m", bold=True) + " Выход")


def create_or_extend(db: Database) -> None:
    fields = db.fields()
    if not fields:
        error("Сначала добавьте названия полей в CoreDB/schema.json.")
        return
    print("\n1 — создать новую запись\n2 — добавить данные в существующую")
    mode = input("Выберите режим: ").strip()
    if mode == "1":
        data = ask_new_data(fields)
        record_id = db.add(data)
        success(f"Запись #{record_id} создана.")
    elif mode == "2":
        record = choose_record(db, "добавления данных")
        if record is None:
            return
        data = dict(record["data"])
        print("Введите значение только для нужных полей. Enter оставляет старое значение.")
        for field in fields:
            value = input(f"{field} [{display(data.get(field))}]: ").strip()
            if value:
                data[field] = value
        db.update(record["id"], data)
        success("Данные добавлены.")
    else:
        error("Режим не выбран.")


def ask_new_data(fields: list[str]) -> dict[str, Any]:
    info("Введите значения полей. Пустой Enter сохранит NULL.")
    return {field: (input(f"Введите {field}: ").strip() or None) for field in fields}


def manage_fields(db: Database) -> None:
    """Показывает текущие поля и позволяет добавить новое через терминал."""
    title("УПРАВЛЕНИЕ СТОЛБЦАМИ")
    info("Текущие поля:")
    for number, field in enumerate(db.fields(), start=1):
        print(f"  {number}. {field}")
    field_name = input("\n  Новое название столбца (Enter — отмена): ").strip()
    if not field_name:
        info("Добавление отменено.")
        return
    if db.add_field(field_name):
        success(f"Столбец «{field_name}» добавлен.")
        info("В старых записях его значение будет отображаться как NULL.")
    elif field_name.casefold() in {field.casefold() for field in db.fields()}:
        error("Такой столбец уже существует.")
    else:
        error("Название столбца не может быть пустым.")


def view_security_log(vault: Vault) -> None:
    clear_screen()
    title("ЖУРНАЛ БЕЗОПАСНОСТИ")
    lines = vault.security_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        info("Событий пока нет.")
        input("\nНажмите Enter для возврата в меню...")
        return
    page_size = 10
    pages = [lines[index:index + page_size] for index in range(0, len(lines), page_size)]
    for page_number, page in enumerate(pages, start=1):
        if page_number > 1:
            clear_screen()
            title("ЖУРНАЛ БЕЗОПАСНОСТИ")
        print(paint(f"  [ PAGE {page_number}/{len(pages)} ]", "\033[91m", bold=True))
        for line in page:
            try:
                event = json.loads(line)
                print(f"  {event['time']}  [{event['event']}]  {event['message']}")
            except (ValueError, KeyError):
                print(f"  {line}")
        if page_number < len(pages):
            input("\nНажмите Enter для следующей страницы...")
        else:
            input("\nНажмите Enter для возврата в меню...")


def view_dossier(db: Database) -> None:
    """Показывает запись как кибер-OSINT досье."""
    record = choose_record(db, "открытия досье")
    if record is None:
        return
    data = record["data"]
    fields = list(dict.fromkeys([*db.fields(), *data]))
    print()
    print(paint("╔══════════════════════════════════════════════════════════════╗", "\033[91m"))
    dossier_line("// INFOCORE :: OSINT CASE FILE")
    print(paint("╠══════════════════════════════════════════════════════════════╣", "\033[91m"))
    dossier_line(f"CASE-ID: IC-{record['id']:06d}   STORAGE: LOCAL")
    print(paint("╠══════════════════════════════════════════════════════════════╣", "\033[91m"))
    sections = (
        ("IDENTITY", ("ФИО", "Дата рождения")),
        ("CONTACT", ("Номер телефона", "ТГ")),
        ("LOCATION", ("Адрес",)),
        ("NOTES / ADDITIONAL DATA", tuple(field for field in fields if field not in {"ФИО", "Дата рождения", "Номер телефона", "ТГ", "Адрес"})),
    )
    used: set[str] = set()
    for section_name, section_fields in sections:
        available = tuple(field for field in section_fields if field in fields)
        if not available:
            continue
        print_dossier_section(section_name)
        for field in available:
            used.add(field)
            print_dossier_field(field, display(data.get(field)))
    for field in fields:
        if field not in used:
            print_dossier_section("ADDITIONAL FIELD")
            print_dossier_field(field, display(data.get(field)))
    print(paint("╠══════════════════════════════════════════════════════════════╣", "\033[91m"))
    print_dossier_section("SYSTEM METADATA")
    print_dossier_field("CREATED", record["created_at"])
    print_dossier_field("UPDATED", record["updated_at"])
    print(paint("╚══════════════════════════════════════════════════════════════╝", "\033[91m"))


def print_dossier_section(name: str) -> None:
    dossier_line(f"[ {name} ]", "\033[91m")


def dossier_line(text: str, color: str = "\033[97m") -> None:
    for paragraph in str(text).splitlines() or [""]:
        clean = "".join(char if char.isprintable() else " " for char in paragraph)
        for line in textwrap.wrap(clean, width=58) or [""]:
            print(paint("║", "\033[91m") + paint(f"  {line:<58}  ", color) + paint("║", "\033[91m"))


def print_dossier_field(field: str, value: str) -> None:
    """Печатает поле досье с переносом длинного значения."""
    dossier_line(f"{field}: {value}")


def edit_record(db: Database) -> None:
    record = choose_record(db, "редактирования")
    if record is None:
        return
    data = dict(record["data"])
    print("Enter оставляет значение без изменений; введите NULL, чтобы очистить поле.")
    for field in db.fields():
        current = display(data.get(field))
        value = input(f"{field} [{current}]: ").strip()
        if value:
            data[field] = None if value.lower() == "null" else value
    db.update(record["id"], data)
    success("Запись обновлена.")


def delete_record(db: Database) -> None:
    record = choose_record(db, "удаления")
    if record is None:
        return
    confirmation = input(f"Удалить запись #{record['id']}? (да/нет): ").strip().lower()
    if confirmation in {"да", "д", "yes", "y"}:
        db.delete(record["id"])
        success("Запись удалена.")
    else:
        info("Удаление отменено.")


def view_data(db: Database) -> None:
    print("\n1 — посмотреть одну запись\n2 — посмотреть всю базу")
    mode = input("Выберите режим: ").strip()
    if mode == "1":
        record = choose_record(db, "просмотра")
        if record:
            print_record(record)
    elif mode == "2":
        records = db.all()
        if not records:
            info("База пока пустая.")
        for record in records:
            print_record(record)
    else:
        error("Режим не выбран.")


def choose_record(db: Database, action: str) -> dict[str, Any] | None:
    try:
        record_id = int(input(f"Введите ID записи для {action}: ").strip())
    except ValueError:
        error("ID должен быть целым числом.")
        return None
    record = db.get(record_id)
    if record is None:
        error("Запись не найдена.")
    return record


def print_record(record: dict[str, Any]) -> None:
    print(f"\n--- Запись #{record['id']} ---")
    for key, value in record["data"].items():
        print(f"{key}: {display(value)}")
    print(f"Создана: {record['created_at']} | Изменена: {record['updated_at']}")


def display(value: Any) -> str:
    return "NULL" if value is None else str(value)
