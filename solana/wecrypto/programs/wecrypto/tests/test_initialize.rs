use {
    anchor_lang::{
        prelude::Pubkey,
        solana_program::{instruction::Instruction, system_program},
        AccountDeserialize, InstructionData, ToAccountMetas,
    },
    litesvm::LiteSVM,
    solana_keypair::Keypair,
    solana_message::{Message, VersionedMessage},
    solana_signer::Signer,
    solana_transaction::versioned::VersionedTransaction,
};

#[test]
fn test_initialize() {
    let program_id = wecrypto::id();
    let payer = Keypair::new();
    let config = Pubkey::find_program_address(
        &[wecrypto::constants::GLOBAL_CONFIG_SEED],
        &program_id,
    )
    .0;
    let mut svm = LiteSVM::new();
    let bytes = include_bytes!(concat!(
        env!("CARGO_TARGET_TMPDIR"),
        "/../deploy/wecrypto.so"
    ));
    svm.add_program(program_id, bytes).unwrap();
    svm.airdrop(&payer.pubkey(), 1_000_000_000).unwrap();

    let idl_uri = "https://idl.uvix-sol.network".to_string();
    let instruction = Instruction::new_with_bytes(
        program_id,
        &wecrypto::instruction::Initialize {
            idl_uri: Some(idl_uri.clone()),
        }
        .data(),
        wecrypto::accounts::Initialize {
            payer: payer.pubkey(),
            config,
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );

    let blockhash = svm.latest_blockhash();
    let msg = Message::new_with_blockhash(&[instruction], Some(&payer.pubkey()), &blockhash);
    let tx = VersionedTransaction::try_new(VersionedMessage::Legacy(msg), &[&payer]).unwrap();

    let res = svm.send_transaction(tx);
    assert!(res.is_ok());

    let config_account = svm.get_account(&config).unwrap();
    let mut data: &[u8] = &config_account.data;
    let config_state = wecrypto::state::GlobalConfig::try_deserialize(&mut data).unwrap();
    assert_eq!(config_state.authority, payer.pubkey());
    assert_eq!(config_state.idl_uri, idl_uri);
    assert!(!config_state.paused);
}
