from db import Database
from interpreter.finalizer import execute_finalizer, ExecuteError
from interpreter.utils import FinalizeState
from node.types import *


async def init_builtin_program(db: Database, program: Program):
    for mapping in program.mappings.keys():
        mapping_id = Field.loads(aleo.get_mapping_id(str(program.id), str(mapping)))
        await db.initialize_builtin_mapping(str(mapping_id), str(program.id), str(mapping))


async def finalize_deploy(confirmed_transaction: ConfirmedTransaction) -> (list, list, str | None):
    CTType = ConfirmedTransaction.Type
    if confirmed_transaction.type == CTType.AcceptedDeploy:
        confirmed_transaction: AcceptedDeploy
        transaction: Transaction = confirmed_transaction.transaction
        transaction: DeployTransaction
        deployment = transaction.deployment
        program = deployment.program
        expected_operations = confirmed_transaction.finalize
        operations = []
        for mapping in program.mappings.keys():
            mapping_id = Field.loads(aleo.get_mapping_id(str(program.id), str(mapping)))
            operations.append({
                "type": FinalizeOperation.Type.InitializeMapping,
                "mapping_id": mapping_id,
                "program_id": program.id,
                "mapping": mapping,
            })
    else:
        raise NotImplementedError
    return expected_operations, operations, None


async def finalize_execute(db: Database, finalize_state: FinalizeState, confirmed_transaction: ConfirmedTransaction,
                           mapping_cache: dict) -> (list, list, str | None):
    CTType = ConfirmedTransaction.Type
    if confirmed_transaction.type == CTType.AcceptedExecute:
        confirmed_transaction: AcceptedExecute
        transaction: Transaction = confirmed_transaction.transaction
        transaction: ExecuteTransaction
        execution = transaction.execution
        expected_operations = confirmed_transaction.finalize
    else:
        confirmed_transaction: RejectedExecute
        if not isinstance(confirmed_transaction.rejected, RejectedExecution):
            raise TypeError("invalid rejected execute transaction")
        execution = confirmed_transaction.rejected.execution
        expected_operations = []
    operations = []
    reject_reason: str | None = None
    for index, transition in enumerate(execution.transitions):
        transition: Transition
        finalize: Vec[Value, u8] = transition.finalize.value
        if finalize is not None:
            program = Program.load(BytesIO(await db.get_program(str(transition.program_id))))
            inputs = list(map(lambda x: x.plaintext, finalize))
            try:
                operations.extend(
                    await execute_finalizer(db, finalize_state, transition.id, program, transition.function_name, inputs, mapping_cache)
                )
            except ExecuteError as e:
                reject_reason = f"execute error: {e}, at transition #{index}, instruction \"{e.instruction}\""
                operations = []
                break
    if confirmed_transaction.type == CTType.RejectedExecute and reject_reason is None:
        raise RuntimeError("rejected execute transaction should not finalize without ExecuteError")
    return expected_operations, operations, reject_reason

async def finalize_block(db: Database, cur, block: Block) -> [str | None]:
    finalize_state = FinalizeState(block)
    mapping_cache = {}
    reject_reasons = []
    for confirmed_transaction in block.transactions.transactions:
        confirmed_transaction: ConfirmedTransaction
        CTType = ConfirmedTransaction.Type
        if confirmed_transaction.type in [CTType.AcceptedDeploy, CTType.RejectedDeploy]:
            expected_operations, operations, reject_reason = await finalize_deploy(confirmed_transaction)
        elif confirmed_transaction.type in [CTType.AcceptedExecute, CTType.RejectedExecute]:
            expected_operations, operations, reject_reason = await finalize_execute(db, finalize_state, confirmed_transaction, mapping_cache)
        else:
            raise NotImplementedError

        for e, o in zip(expected_operations, operations):
            if e.type != o["type"]:
                raise TypeError("invalid finalize operation type")
            if e.mapping_id != o["mapping_id"]:
                raise TypeError("invalid finalize mapping id")
            match e.type:
                case FinalizeOperation.Type.InitializeMapping:
                    pass
                case FinalizeOperation.Type.UpdateKeyValue:
                    if e.index != o["index"] or e.key_id != o["key_id"] or e.value_id != o["value_id"]:
                        raise TypeError("invalid finalize operation")
                case _:
                    raise NotImplementedError

        await execute_operations(db, cur, operations)
        reject_reasons.append(reject_reason)
    return reject_reasons


async def execute_operations(db: Database, cur, operations: [dict]):
    for operation in operations:
        match operation["type"]:
            case FinalizeOperation.Type.InitializeMapping:
                mapping_id = operation["mapping_id"]
                program_id = operation["program_id"]
                mapping = operation["mapping"]
                await db.initialize_mapping(cur, str(mapping_id), str(program_id), str(mapping))
            case FinalizeOperation.Type.UpdateKeyValue:
                mapping_id = operation["mapping_id"]
                index = operation["index"]
                key_id = operation["key_id"]
                value_id = operation["value_id"]
                key = operation["key"]
                value = operation["value"]
                await db.update_mapping_key_value(cur, str(mapping_id), index, str(key_id), str(value_id), key.dump(), value.dump())
            case _:
                raise NotImplementedError

async def preview_finalize_execution(db: Database, program: Program, function_name: Identifier, inputs: [Value]) -> [FinalizeOperation]:
    block = await db.get_latest_block()
    finalize_state = FinalizeState(block)
    return await execute_finalizer(db, finalize_state, TransitionID.load(BytesIO(b"\x00" * 32)), program, function_name, inputs, {})