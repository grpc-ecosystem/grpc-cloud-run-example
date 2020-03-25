mod protos;

use std::{env, thread};

use protos::calculator::{BinaryOperation, CalculationResult, Operation};
use protos::calculator_grpc::{Calculator, CalculatorServer};

use grpc::{RequestOptions, ServerBuilder, SingleResponse};

pub struct CalculatorImpl;
impl Calculator for CalculatorImpl {
    fn calculate(
        &self,
        _: RequestOptions,
        rqst: BinaryOperation,
    ) -> SingleResponse<CalculationResult> {
        let op1: f32 = rqst.get_first_operand();
        let op2: f32 = rqst.get_second_operand();
        let result: f32 = match rqst.get_operation() {
            Operation::ADD => op1 + op2,
            Operation::SUBTRACT => op1 - op2,
        };
        let resp = CalculationResult {
            result: result,
            ..Default::default()
        };
        return SingleResponse::completed(resp);
    }
}

fn main() {
    let err = "Unable to parse `PORT` environment variable value, expecting a value that parses to a 16-bit integer (0..65535)";
    let key = "PORT";
    let port = match env::var_os(key) {
        Some(val) => match val.to_str() {
            Some(s) => match s.parse::<u16>() {
                Ok(p) => p,
                Err(_) => panic!(err),
            },
            None => panic!(err),
        },
        // `PORT` environment variable unset; defaulting to...
        None => 50051,
    };

    let mut server = ServerBuilder::new_plain();
    server.http.set_port(port);
    server.add_service(CalculatorServer::new_service_def(CalculatorImpl));
    let _server = server.build().expect("server");

    println!("Starting: gRPC Listener [{}]", port);

    loop {
        thread::park();
    }
}
