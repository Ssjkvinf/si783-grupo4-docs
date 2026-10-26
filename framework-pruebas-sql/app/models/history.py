"""
Modelo de base de datos para registrar la trazabilidad completa de las ejecuciones.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class ExecutionHistory(Base):
    __tablename__ = "execution_history"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, default=1)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=True)
    connection_profile_id = Column(Integer, ForeignKey("connection_profiles.id"), nullable=True)
    
    status = Column(String, index=True, nullable=False)  # PASS, FAIL, ERROR
    executed_at = Column(DateTime(timezone=True), default=get_utc_now, index=True)
    duration_ms = Column(Float, nullable=False)
    
    statement_type = Column(String, nullable=True)
    executed_sql = Column(Text, nullable=False)
    validation_type = Column(String, nullable=True)
    expected_result = Column(String, nullable=True)
    actual_result = Column(Text, nullable=True)
    rowcount = Column(Integer, default=0)
    rollback_applied = Column(Boolean, default=False)
    rollback_error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Origen de la ejecución: UI (módulos Casos/Suites), INICIO (recorrido guiado), CLI o GITHUB_ACTIONS.
    # NULL = registro anterior a la Fase 4 (origen no registrado).
    trigger_source = Column(String, nullable=True, index=True)
    # Identifica una corrida (todas las filas de una misma ejecución de suite o de la CLI comparten run_id).
    run_id = Column(String, nullable=True, index=True)
    # Usuario que lanzó la ejecución (o «cli» / «github-actions»). NULL = sin control de acceso o registro anterior.
    executed_by = Column(String(50), nullable=True, index=True)

    project = relationship("Project", back_populates="execution_histories")
    test_case = relationship("TestCase", back_populates="execution_histories")
    test_suite = relationship("TestSuite", back_populates="execution_histories")
    connection_profile = relationship("ConnectionProfile", back_populates="execution_histories")

    # Nombres legibles para la interfaz (el historial se listaba con IDs como «C-12 / S-3»).
    @property
    def case_name(self):
        return self.test_case.name if self.test_case is not None else None

    @property
    def suite_name(self):
        return self.test_suite.name if self.test_suite is not None else None

    @property
    def connection_name(self):
        return self.connection_profile.name if self.connection_profile is not None else None